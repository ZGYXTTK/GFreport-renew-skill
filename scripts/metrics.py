# -*- coding: utf-8 -*-
"""
metrics.py —— 跨月度量记录（v1）

runs/metrics.json：按月落盘每期 9 道门禁的得分与通道降级次数，
便于跨期 trend 对比。
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
_BASE = _HERE.parent
_METRICS_FILE = _BASE / 'runs' / 'metrics.json'


def _read():
    if _METRICS_FILE.exists():
        return json.loads(_METRICS_FILE.read_text(encoding='utf-8'))
    return []


def _write(data):
    _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _METRICS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def record(ym, run_id, gate_scores, downgrades=0):
    """记录一期度量。
    gate_scores: dict，键为门禁名，值为 0/1/2 (0=通过 / 1=硬失败 / 2=跳过)
    """
    data = _read()
    data.append({
        'ym': ym,
        'run_id': run_id,
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        'gate_scores': gate_scores,
        'downgrades': downgrades,
    })
    _write(data)
    print(f'✅ metrics 已记录：{ym} / {run_id}（共 {len(data)} 期）')


def trend():
    """打印跨月趋势表。"""
    data = _read()
    if not data:
        print('⚠️  暂无 metrics')
        return
    print('| ym | run_id | 通过 | 硬失败 | 跳过 | 降级 |')
    print('| --- | --- | --- | --- | --- | --- |')
    for m in data:
        scores = m['gate_scores']
        passed = sum(1 for v in scores.values() if v == 0)
        failed = sum(1 for v in scores.values() if v == 1)
        skipped = sum(1 for v in scores.values() if v == 2)
        print(f"| {m['ym']} | {m['run_id'][:24]} | {passed} | {failed} | {skipped} | {m['downgrades']} |")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='action', required=True)

    p1 = sub.add_parser('record')
    p1.add_argument('--ym', required=True)
    p1.add_argument('--run-id', required=True)
    p1.add_argument('--gates', required=True, help='格式：g1=0,g2=1,...')
    p1.add_argument('--downgrades', type=int, default=0)

    sub.add_parser('trend')

    args = ap.parse_args()
    if args.action == 'record':
        scores = {}
        for kv in args.gates.split(','):
            k, v = kv.split('=')
            scores[k.strip()] = int(v)
        record(args.ym, args.run_id, scores, args.downgrades)
    else:
        trend()


if __name__ == '__main__':
    main()