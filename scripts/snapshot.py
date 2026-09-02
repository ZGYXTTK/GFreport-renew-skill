# -*- coding: utf-8 -*-
"""
snapshot.py —— 口径快照 + 叶子级深 diff（v1）

每月初把所有 config/*.json 序列化落盘到 config/口径快照/<YYYY-MM>.json，
便于跨月对比 + 漂移检测。叶子级深 diff ≥3 项触发「暂停确认」。
"""
import datetime
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from adapt_json import (
    load_endpoints, load_tool_registry, load_collection_list,
    load_authority_source_map, load_caliber_dict,
    load_timepoint_alignment, load_target_pool, load_channels,
)

_BASE = _HERE.parent
_SNAPSHOT_DIR = _BASE / 'config' / '口径快照'


def _all_configs():
    return {
        'endpoints.json': load_endpoints(),
        'tool_registry.json': load_tool_registry(),
        '采集清单.json': load_collection_list(),
        '权威源映射.json': load_authority_source_map(),
        '口径字典.json': load_caliber_dict(),
        '时点对齐.json': load_timepoint_alignment(),
        '标的池.json': load_target_pool(),
        'channels.json': load_channels(),
    }


def _deep_diff(a, b, path=''):
    """返回 [(path, a_value, b_value), ...] 叶子级差异。"""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            diffs.extend(_deep_diff(a.get(k), b.get(k), f'{path}.{k}' if path else k))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((f'{path}.len', len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diffs.extend(_deep_diff(x, y, f'{path}[{i}]'))
    elif a != b:
        diffs.append((path, a, b))
    return diffs


def take_snapshot(ym):
    """落盘当前 config 快照到 config/口径快照/<YYYY-MM>.json。"""
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snap_path = _SNAPSHOT_DIR / f'{ym}.json'
    data = {
        'ym': ym,
        'taken_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'configs': _all_configs(),
    }
    snap_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ 快照已落盘：{snap_path}')
    return snap_path


def diff_snapshot(ym, prev_ym):
    """对比两个月的快照，返回差异列表。"""
    cur = _SNAPSHOT_DIR / f'{ym}.json'
    prev = _SNAPSHOT_DIR / f'{prev_ym}.json'
    if not prev.exists():
        print(f'⚠️  上期快照不存在：{prev}（首次运行无 diff）')
        return []
    if not cur.exists():
        print(f'⚠️  本期快照不存在：{cur}（先 take_snapshot）')
        return []

    a = json.loads(prev.read_text(encoding='utf-8'))['configs']
    b = json.loads(cur.read_text(encoding='utf-8'))['configs']
    diffs = _deep_diff(a, b)
    print(f'✅ 快照对比：{prev_ym} → {ym} ｜ {len(diffs)} 项叶子级差异')
    if diffs:
        for d in diffs[:30]:
            print(f'  - {d[0]}：{d[1]!r} → {d[2]!r}')
        if len(diffs) > 30:
            print(f'  … 还有 {len(diffs) - 30} 项')
        if len(diffs) >= 3:
            print(f'⚠️  差异 ≥3 项，需用户确认（纪律 P0-10）')
    return diffs


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['snapshot', 'diff'])
    ap.add_argument('--ym', required=True, help='YYYY-MM')
    ap.add_argument('--prev-ym', help='对比月份')
    args = ap.parse_args()

    if args.action == 'snapshot':
        take_snapshot(args.ym)
    elif args.action == 'diff':
        if not args.prev_ym:
            raise SystemExit('diff 模式需 --prev-ym')
        diff_snapshot(args.ym, args.prev_ym)


if __name__ == '__main__':
    main()