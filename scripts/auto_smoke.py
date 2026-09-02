# -*- coding: utf-8 -*-
"""
auto_smoke.py —— 通道实测自动回写（v0.1.0 必修）

实战背景：channel_health.py 报告里 11 个 MCP/agent 通道标 🟡（待实测）。
本脚本调用各 MCP 通道并回写 sources/通道实测.jsonl，让 channel_health 转为 ✅。

策略：
1. 读 config/endpoints.json 的 mcp / agent 段
2. 对每个工具，按 smoke_hint 调用一次（如果可识别）
3. 把成功/失败/超时结果写到 sources/通道实测.jsonl（key=channel name, status=ok/degraded/fail）
4. 重新跑 channel_health.py，统计 🟡→✅ 转换数

注：实际调用 MCP 需要 DSH Agent 在主流程中触发；本脚本生成 expected_smokecalls.jsonl
作为"待实测清单"，供 Agent 在主流程中按清单逐个实测并写回 results.jsonl。
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
import adapt_json  # noqa: E402

_BASE = _HERE.parent
_CONFIG = _BASE / 'config'


def _build_smokecall_list():
    """从 endpoints.json 提取所有 MCP/agent 通道，生成待实测清单。"""
    ep = adapt_json.load_endpoints()
    registry = adapt_json.load_tool_registry()

    items = []
    # MCP 通道
    for ch in ep.get('mcp', []):
        items.append({
            'channel': ch['name'],
            'type': 'mcp',
            'smoke_hint': ch.get('smoke_hint', ''),
            'note': ch.get('note', ''),
        })
    # Agent 通道
    for ch in ep.get('agent', []):
        items.append({
            'channel': ch['name'],
            'type': 'agent',
            'smoke_hint': ch.get('smoke_hint', ''),
            'note': ch.get('note', ''),
        })
    return items


def main():
    ap = argparse.ArgumentParser(description='通道实测自动回写')
    ap.add_argument('--out', default=None,
                    help='通道实测.jsonl 输出路径（默认 <run-id>/sources/通道实测.jsonl）')
    ap.add_argument('--run-id', default=None,
                    help='run-id（默认扫描 runs/ 最新）')
    args = ap.parse_args()

    items = _build_smokecall_list()
    print(f'📋 待实测通道：{len(items)} 个')

    # 解析 smoke_hint 推断建议调用方式
    plan_path = Path(args.out) if args.out else (
        _BASE / 'runs' / (args.run_id or 'latest') / 'sources' / '通道实测.jsonl'
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps({
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'note': 'agent 应按 smoke_hint 逐个调用本文件 channels 列表中的通道，并回写 status',
        'channels': items,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ 待实测清单：{plan_path}')
    print()
    print('下一步：DSH Agent 按 smoke_hint 实测每个通道，然后把 results 写到：')
    print(f'  {plan_path.parent / "通道实测_results.jsonl"}')
    print()
    print('results.jsonl 格式（每行一条）：')
    print(json.dumps({
        'channel': 'mcp__stock-sdk__get_a_share_quotes',
        'status': 'ok',
        'detail': 'HTTP 200, 取 600760.SH 实时行情成功',
        'tested_at': '2026-08-31T22:13:00',
        'source_tool': 'mcp__stock-sdk__get_a_share_quotes',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
