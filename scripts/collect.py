# -*- coding: utf-8 -*-
"""
collect.py — 数据采集调度（v1 · 占位实现）

MVP：仅打印「应采集的项 + 计划通道 + 输出文件」，由 Agent 在 prompt 里执行真实调用。
v1.1：将替换为 fan-out 子 Agent 调度器。

设计约束：
  - 不在本进程内调 MCP（MCP 只能由宿主 Agent 调用）
  - 仅落「采集计划」jsonl + 「采集结果」jsonl 占位文件
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from adapt_json import load_collection_list, load_endpoints, load_authority_source_map

_BASE = _HERE.parent


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


def plan(ym, run_id):
    """落盘「采集计划」jsonl：每条 = 一个采集项 + 通道映射。"""
    coll = load_collection_list()
    valid = _valid_channels()
    out_dir = _BASE / 'runs' / run_id / 'download'
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / '采集计划.jsonl'

    rows = []
    for item in coll.get('items', []):
        chs = item['通道']
        valid_chs = [c for c in chs if c in valid]
        invalid_chs = [c for c in chs if c not in valid]
        rows.append({
            'ym': ym,
            'id': item['id'],
            '类型': item['类型'],
            '通道': chs,
            'valid_channels': valid_chs,
            'invalid_channels': invalid_chs,
            '口径': item['口径'],
            '输出': item.get('输出', ''),
            '状态': 'plan',
            'as_of': coll.get('截至日期', ''),
        })
    plan_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
    print(f'✅ 采集计划已落盘：{plan_path}（{len(rows)} 项）')
    if any(r['invalid_channels'] for r in rows):
        print('⚠️  以下通道名不在 endpoints.json，需补：')
        for r in rows:
            if r['invalid_channels']:
                print(f"   {r['id']}: {r['invalid_channels']}")
    return plan_path


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='action', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--ym', required=True)
    p.add_argument('--run-id', required=True)
    args = ap.parse_args()
    if args.action == 'plan':
        plan(args.ym, args.run_id)


if __name__ == '__main__':
    main()