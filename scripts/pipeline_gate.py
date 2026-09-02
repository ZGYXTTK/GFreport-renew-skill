# -*- coding: utf-8 -*-
"""
pipeline_gate.py —— P0 纪律的结构性 guard（v2：读 gate_state.json 实际内容）

archive_to_workspace.py 之前自动检查可自动验证的 P0 纪律：
  P0-3  工具盘点先于标 ✅
  P0-5  数值回读通过
  P0-7  盲审通过（reviews/独立审核意见.md 必须存在且无阻断级）
  P0-8  格式对齐 ≥95%
  P0-9  空值必补
  P0-11 产出必达工作区

未通过 → exit 1（archive 必须等通过后才能执行）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_RUNS = _BASE / 'runs'

P0_CHECKS = [
    ('P0-3  工具盘点先于标 ✅',          'tools'),
    ('P0-5  数值回读通过',                'gate:08_verify_value'),
    ('P0-7  盲审通过',                    'blind_review'),
    ('P0-8  格式对齐 ≥95%',               'gate:07_format_diff'),
    ('P0-9  空值必补',                    'gate:03_diff_empty'),
    ('P0-11 产出必达工作区',              'archive_done'),
]


def _gate_state(run_id):
    p = _RUNS / run_id / 'gate_state.json'
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}


def _check_tools_smoke(run_id):
    inv = _RUNS / run_id / 'sources' / '工具清单.jsonl'
    if not inv.exists():
        return False, '工具清单.jsonl 缺失（Step 2 未完成）'
    has_discovered = False
    for line in inv.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get('discovered'):
            has_discovered = True
            break
    if not has_discovered:
        return False, 'kind=registry 源未 discover'
    return True, 'kind=registry 源已 discover'


def _check_gate(run_id, gate_key):
    state = _gate_state(run_id)
    info = state.get(gate_key, {})
    code = info.get('code')
    if code == 0:
        return True, f'{gate_key} code=0'
    if code == 2:
        return False, f'{gate_key} SKIPPED（不满足前置条件）'
    if code is None:
        return False, f'{gate_key} 未执行'
    return False, f'{gate_key} code={code}'


def _check_blind_review(run_id):
    review = _RUNS / run_id / 'reviews' / '独立审核意见.md'
    if not review.exists():
        return False, 'reviews/独立审核意见.md 缺失（Step 8 未完成）'
    text = review.read_text(encoding='utf-8')
    if re.search(r'阻断级[：:]\s*[1-9]', text):
        return False, '审核意见含阻断级问题'
    if re.search(r'阻断级[：:]\s*\d+\s*项', text):
        return False, '审核意见含阻断级问题'
    if not any(marker in text for marker in ('通过', '✅', '无阻断')):
        return False, '审核意见未明确为"通过"'
    return True, '盲审通过'


def _check_archive_done(run_id):
    mf = _RUNS / run_id / 'manifest.json'
    if not mf.exists():
        return False, 'manifest.json 缺失'
    try:
        m = json.loads(mf.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return False, 'manifest.json 解析失败'
    pre = m.get('preconditions', {})
    if pre.get('archive_done') is True:
        return True, 'archive_done=true'
    return False, 'archive_done 未置位'


CHECK_DISPATCH = {
    'tools': _check_tools_smoke,
    'blind_review': _check_blind_review,
    'archive_done': _check_archive_done,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()

    fails = []
    print(f'P0 守卫 · {args.run_id}\n')
    for label, key in P0_CHECKS:
        if key in CHECK_DISPATCH:
            ok, detail = CHECK_DISPATCH[key](args.run_id)
        elif key.startswith('gate:'):
            ok, detail = _check_gate(args.run_id, key[len('gate:'):])
        else:
            ok, detail = False, f'unknown check key: {key}'
        icon = '✅' if ok else '❌'
        print(f'  {icon} {label}：{detail}')
        if not ok:
            fails.append(label)

    if fails:
        print(f'\n❌ {len(fails)} 项 P0 不通过：{fails}')
        print('   archive_to_workspace.py 必须等待这些 P0 通过后再执行。')
        sys.exit(1)
    print('\n✅ 6 项可自动验证 P0 全部通过；剩余 5 条（P0-1/2/4/6/10）由 Agent 自觉 + 盲审把关。')
    print('   可执行 archive_to_workspace.py。')


if __name__ == '__main__':
    main()