# -*- coding: utf-8 -*-
"""
manifest.py —— 运行契约（runs/<run-id>/manifest.json）

子 Skill 只读它，不靠"传路径/参数"。
"""
import datetime
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
_BASE = _HERE.parent
_RUNS = _BASE / 'runs'


def _run_dir(run_id):
    d = _RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(run_id):
    return _run_dir(run_id) / 'manifest.json'


def init_run(run_id, ym, pack='_default', old_doc=None):
    """初始化 manifest（首次创建）。"""
    p = _manifest_path(run_id)
    if p.exists():
        print(f'⚠️  manifest 已存在：{p}（不会覆盖）')
        return json.loads(p.read_text(encoding='utf-8'))

    data = {
        'run_id': run_id,
        'ym': ym,
        'pack': pack,
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'input': {'old_doc': old_doc} if old_doc else {},
        'preconditions': {
            'channel_health_done': False,
            'tool_inventory_done': False,
            'config_validated': False,
            'snapshot_taken': False,
            'archive_done': False,
        },
        'gates': {},
        'outputs': {},
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ manifest 已初始化：{p}')
    return data


def get_field(run_id, key=None):
    """读 manifest.json；key 不传则返回整个 dict。"""
    p = _manifest_path(run_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding='utf-8'))
    if key is None:
        return data
    if '.' in key:
        parts = key.split('.')
        v = data
        for part in parts:
            v = v.get(part) if isinstance(v, dict) else None
            if v is None:
                return None
        return v
    return data.get(key)


def set_field(run_id, key, value):
    """写 manifest 字段。key 支持「a.b.c」点号路径。"""
    p = _manifest_path(run_id)
    if not p.exists():
        raise SystemExit(f'❌ manifest 不存在：{p}（先 init_run）')
    data = json.loads(p.read_text(encoding='utf-8'))
    if '.' in key:
        parts = key.split('.')
        node = data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    else:
        data[key] = value
    data['updated_at'] = datetime.datetime.now().isoformat(timespec='seconds')
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def gate_result(run_id, gate, code, detail=None):
    """记录单个门禁的执行结果。code: 0=通过 / 1=硬失败 / 2=跳过。"""
    p = _manifest_path(run_id)
    if not p.exists():
        raise SystemExit(f'❌ manifest 不存在：{p}')
    data = json.loads(p.read_text(encoding='utf-8'))
    data.setdefault('gates', {})[gate] = {
        'code': code,
        'detail': detail or '',
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['init', 'get', 'set', 'gate'])
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--ym', default=None)
    ap.add_argument('--pack', default='_default')
    ap.add_argument('--old-doc', default=None)
    ap.add_argument('--key', default=None)
    ap.add_argument('--value', default=None)
    ap.add_argument('--code', type=int, default=0)
    ap.add_argument('--detail', default=None)
    args = ap.parse_args()

    if args.action == 'init':
        init_run(args.run_id, args.ym or '', pack=args.pack, old_doc=args.old_doc)
    elif args.action == 'get':
        v = get_field(args.run_id, args.key)
        print(json.dumps(v, ensure_ascii=False, indent=2) if v is not None else 'null')
    elif args.action == 'set':
        if not args.key:
            raise SystemExit('--key 必填')
        set_field(args.run_id, args.key, args.value)
        print(f'✅ set {args.key} = {args.value}')
    elif args.action == 'gate':
        if not args.key:
            raise SystemExit('--key 必填（gate 名）')
        gate_result(args.run_id, args.key, args.code, args.detail)
        print(f'✅ gate {args.key} → code={args.code}')


if __name__ == '__main__':
    main()