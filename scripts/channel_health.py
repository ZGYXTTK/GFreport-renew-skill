# -*- coding: utf-8 -*-
"""
channel_health.py —— 通道健康度自检（v1）

HTTP 通道：脚本直接探测；
MCP / agent 通道：Agent 实测后回写 通道实测.jsonl，脚本只校验新鲜度。
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from adapt_json import load_endpoints, load_channels

_BASE = _HERE.parent
_STATE_DIR = _BASE / 'state'
_HISTORY = _STATE_DIR / '渠道历史.jsonl'

_STATUS_MAP = {'ok': '✅', 'degraded': '🟡', 'fail': '❌'}


def probe_http(url, method, headers=None, body=None, timeout=10):
    if requests is None:
        return False, 'requests 未安装'
    try:
        if method.upper() == 'GET':
            r = requests.get(url, headers=headers or {}, timeout=timeout)
        else:
            r = requests.post(url, headers=headers or {}, data=body or {}, timeout=timeout)
        ok = 200 <= r.status_code < 400 and len(r.content) > 0
        return ok, f'HTTP {r.status_code}, {len(r.content)} bytes'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def load_mcp_log(path):
    """加载 MCP 通道实测记录（v0.1.0 重构：兼容多路径 + 多格式）。

    支持的格式：
    1. line-of-jsonl：每行一条 {channel, status, tested_at, detail}
    2. dict-of-dict：auto_smoke.py 输出的 {"channels": {name: rec}}

    支持的路径（按优先级合并）：
    1. --mcp-log 显式指定
    2. runs/<run-id>/sources/通道实测_results.jsonl（实测结果）
    3. runs/<run-id>/sources/通道实测.jsonl（实测计划，dict-of-dict）
    """
    latest = {}

    def _merge_file(p: Path):
        if not p.exists():
            return
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = p.read_text(encoding='gbk', errors='ignore')
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 兼容 dict-of-dict 格式（auto_smoke.py 输出）
            if isinstance(rec, dict) and 'channels' in rec:
                for ch_name, ch_rec in rec['channels'].items():
                    latest[ch_name] = ch_rec
                continue
            ch = rec.get('channel')
            ts = rec.get('tested_at', '')
            if ch and (ch not in latest or ts >= latest[ch].get('tested_at', '')):
                latest[ch] = rec

    # v0.1.0 重构：合并多个路径（实测结果 + 计划 + auto_smoke 列表）
    paths_to_try = []
    if path:
        paths_to_try.append(Path(path))
    # 默认查找 run-dir 下的实测结果
    p_run = _BASE / 'runs' / '__RUN_ID_PLACEHOLDER__'
    for cand in [
        _BASE / 'sources' / '通道实测_results.jsonl',
        _BASE / 'sources' / '通道实测.jsonl',
        _BASE / 'sources' / 'smoke_results.jsonl',
    ]:
        if cand.exists():
            paths_to_try.append(cand)

    for p in paths_to_try:
        _merge_file(p)
    return latest


def resolve_agent_channel(name, latest, max_age_days, today):
    rec = latest.get(name)
    if not rec:
        return '🟡', '待实测：Agent 需按 endpoints.json 的 smoke_hint 真调一次并回写 通道实测.jsonl', True
    ts = rec.get('tested_at', '')
    try:
        age = (today - datetime.date.fromisoformat(ts)).days
    except ValueError:
        return '🟡', f'实测记录日期非法：{ts!r}', True
    if age > max_age_days:
        return '🟡', f'实测记录过期（{ts}，{age} 天前），本期需重测', True
    st = _STATUS_MAP.get(str(rec.get('status', '')).lower(), '🟡')
    return st, f'实测于 {ts}：{rec.get("detail", "")[:60]}', False


def append_history(ym, results):
    _STATE_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    with open(_HISTORY, 'a', encoding='utf-8') as f:
        for name, status, _detail, _flag in results:
            f.write(json.dumps({'ym': ym, 'channel': name, 'status': status, 'ts': ts}, ensure_ascii=False) + '\n')


def consecutive_fail_months(channel, ym_now):
    if not _HISTORY.exists():
        return 0
    by_month = {}
    for line in _HISTORY.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get('channel') == channel:
            by_month[rec.get('ym', '')] = rec.get('status', '')
    months = sorted(m for m in by_month if m and m <= ym_now)
    streak = 0
    for m in reversed(months):
        if by_month[m] == '❌':
            streak += 1
        else:
            break
    return streak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ym', required=True)
    ap.add_argument('--run-id', default='unknown')
    ap.add_argument('--mcp-log', default=None)
    ap.add_argument('--max-age-days', type=int, default=35)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    today = datetime.date.today()
    ep = load_endpoints()
    mcp_log = args.mcp_log
    if not mcp_log:
        cands = [
            _BASE / 'runs' / args.run_id / 'sources' / '通道实测.jsonl',
            _STATE_DIR / '通道实测.jsonl',
        ]
        mcp_log = next((str(c) for c in cands if c.exists()), str(cands[0]))
    latest = load_mcp_log(mcp_log)

    out_path = Path(args.out) if args.out else (_BASE / 'runs' / args.run_id / f'通道健康度-{args.ym}.md')
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for ch in ep.get('http', []) or []:
        ok, detail = probe_http(ch['url'], ch.get('method', 'GET'), ch.get('headers'), ch.get('body'))
        status = '✅' if ok else '❌'
        if not ok and ch.get('note'):
            detail += f'（{ch["note"]}）'
        results.append((ch['name'], status, detail, False))

    need_test_list = []
    for group in ('mcp', 'agent'):
        for ch in ep.get(group, []) or []:
            status, detail, need = resolve_agent_channel(ch['name'], latest, args.max_age_days, today)
            if need:
                hint = ch.get('smoke_hint', '')
                need_test_list.append(f'{ch["name"]}（{hint}）' if hint else ch['name'])
            results.append((ch['name'], status, detail, need))

    append_history(args.ym, results)

    streak_notes = []
    for name, status, _d, _n in results:
        if status == '❌':
            streak = consecutive_fail_months(name, args.ym)
            if streak >= 2:
                streak_notes.append(f'{name} 已连续 {streak} 期 ❌ → 触发「续费 / 改接口」提示')

    lines = [
        f'# 通道健康度 · {args.ym} 月（channel_health.py v1）',
        f'生成时间：{datetime.datetime.now().isoformat(timespec="seconds")} ｜ 运行 ID：{args.run_id} ｜ 实测日志：{mcp_log}',
        '',
        '| 通道 | 状态 | 详情 |',
        '| --- | --- | --- |',
    ]
    for name, status, detail, _n in results:
        lines.append(f'| {name} | {status} | {detail[:90]} |')
    bad = [r[0] for r in results if r[1] == '❌']
    lines += ['', f'## 统计：✅{sum(1 for r in results if r[1] == "✅")} 🟡{sum(1 for r in results if r[1] == "🟡")} ❌{len(bad)}']
    if need_test_list:
        lines += ['', '## 本期必须实测（Agent 真调一次并回写 通道实测.jsonl）', '']
        for n in need_test_list:
            lines.append(f'- {n}')
    if streak_notes:
        lines += ['', '## 连续失败触发', '']
        for n in streak_notes:
            lines.append(f'- ❌ {n}')
    if bad:
        lines += ['', '## 失败通道（本期按降级链执行）', '']
        for n in bad:
            lines.append(f'- {n}')

    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f'✅ 通道健康度报告：{out_path}')
    print(f'   ✅{sum(1 for r in results if r[1] == "✅")} 🟡{sum(1 for r in results if r[1] == "🟡")} ❌{len(bad)} ｜ 待实测 {len(need_test_list)} ｜ 连续❌触发 {len(streak_notes)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())