# -*- coding: utf-8 -*-
"""
tool_inventory.py —— Step 2 工具盘点机检（v1）

校验 Agent 写出的 工具清单.jsonl：
  - 注册表内每个源必须出现
  - kind=registry 的源必须 discovered=true 且有 found_tools
  - smoke=none 的源必须标 🟡 而非 ✅
"""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from adapt_json import load_tool_registry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inventory', required=True, help='工具清单.jsonl 路径')
    ap.add_argument('--out', default='tool_inventory_report.md')
    args = ap.parse_args()

    if not Path(args.inventory).exists():
        Path(args.out).write_text(f'# 工具清单校验\n\n清单不存在：{args.inventory}\n', encoding='utf-8')
        return

    inv = []
    for line in Path(args.inventory).read_text(encoding='utf-8').splitlines():
        line = line.strip().lstrip('\ufeff')
        if not line:
            continue
        try:
            inv.append(json.loads(line))
        except json.JSONDecodeError:
            inv.append({'_raw':line, '_parse_fail': True})

    inv_by_source = {r.get('source'): r for r in inv if r.get('source') and not r.get('_parse_fail')}

    registry = load_tool_registry()
    sources = registry.get('sources', [])
    problems = []
    warnings = []
    uncovered = []

    for s in sources:
        name = s.get('name')
        kind = s.get('kind', 'api')
        rec = inv_by_source.get(name)
        if rec is None:
            problems.append(f'注册表源「{name}」未盘点')
            continue
        if rec.get('present') is False:
            warnings.append(f'注册表源「{name}」标记未安装')
            continue
        if kind == 'registry' and not rec.get('discovered'):
            problems.append(f'聚合源「{name}」未探查（discover 缺失）')
        elif kind == 'registry' and rec.get('discovered') and not rec.get('found_tools'):
            warnings.append(f'聚合源「{name}」discovered=true 但 found_tools 为空')
        if rec.get('smoke') == 'none':
            warnings.append(f'源「{name}」未 smoke test')

    listed = {s.get('name') for s in sources}
    for name in inv_by_source:
        if name not in listed:
            uncovered.append(name)

    lines = [
        '# 工具清单校验报告（tool_inventory.py v1）',
        f'清单源数：{len(inv)} ｜ 注册表源数：{len(sources)}',
        f'阻断：{len(problems)} ｜ 警告：{len(warnings)} ｜ 未列：{len(uncovered)}',
        '',
    ]
    if problems:
        lines.append('## 阻断（必补）')
        for p in problems:
            lines.append(f'- ❌ {p}')
    if warnings:
        lines.append('## 警告')
        for w in warnings:
            lines.append(f'- ⚠️ {w}')
    if uncovered:
        lines.append('## 本机有 / 注册表未列')
        for u in uncovered:
            lines.append(f'- 💡 {u}')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    print(f'清单 {len(inv)} 源 ｜ 阻断 {len(problems)} ｜ 警告 {len(warnings)}（{args.out}）')
    if problems:
        sys.exit(1)


if __name__ == '__main__':
    main()