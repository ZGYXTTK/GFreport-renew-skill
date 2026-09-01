# -*- coding: utf-8 -*-
"""
config_check.py —— ② 配置校验门禁（v1）

校验采集清单中每个 item 的通道名必须出现在 endpoints.json 中。
硬门禁：发现未声明通道名 → exit 1。
"""
import argparse
import datetime
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent.parent
sys.path.insert(0, str(_HERE))
from adapt_json import load_collection_list, load_endpoints


def _valid_channels():
    ep = load_endpoints()
    valid = set()
    for ch in ep.get('http', []) or []:
        valid.add(ch['name'])
    for ch in ep.get('mcp', []) or []:
        valid.add(ch['name'])
    for ch in ep.get('agent', []) or []:
        valid.add(ch['name'])
    return valid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='02_config_check.md')
    ap.add_argument('--run-id', default=None, help='写入 manifest gate 状态（可选）')
    args = ap.parse_args()

    coll = load_collection_list()
    valid = _valid_channels()

    items = coll.get('items', [])
    problems = []
    for item in items:
        for ch in item.get('通道', []):
            if ch not in valid:
                problems.append(f'{item["id"]}: 通道「{ch}」未在 endpoints.json 中声明')

    if not items:
        problems.append('采集清单为空（items 为空数组）')

    lines = [
        '# 配置校验报告（config_check.py v1）',
        f'校验日期：{datetime.datetime.now().isoformat(timespec="seconds")}',
        f'采集项：{len(items)} ｜ 有效通道：{len(valid)}',
        '',
        '| 采集项 | 类型 | 通道 | 通道有效性 |',
        '| --- | --- | --- | --- |',
    ]
    for item in items:
        chs = item.get('通道', [])
        bad = [c for c in chs if c not in valid]
        v = '✅' if not bad else '❌'
        lines.append(f"| {item['id']} | {item['类型']} | {', '.join(chs)} | {v} |")

    if problems:
        lines += ['', '## 阻断问题']
        for p in problems:
            lines.append(f'- ❌ {p}')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')

    if problems:
        print(f'❌ 配置校验失败：{len(problems)} 项问题（{args.out}）')
        sys.exit(1)
    print(f'✅ 配置校验通过：{len(items)} 项采集 / {len(valid)} 个通道（{args.out}）')


if __name__ == '__main__':
    main()