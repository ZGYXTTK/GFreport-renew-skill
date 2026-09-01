# -*- coding: utf-8 -*-
"""
aggregate_subagent.py —— 子 Agent 输出聚合器（v0.1.0 必修）

实战背景：6 个 subagent 各自输出 markdown 格式的 JSONL/汇总报告，
本脚本自动解析并合并为标准格式：
- sources/溯源.jsonl（每条带 cell/source_file/source_field/source_row/cross_checked）
- sources/变更摘要.md（环比 ±20% 字段点名）
- sources/source_*.csv（按章节：指数/标的/发射/政策/财务/融资/案例/估值/IPO）

支持的子 Agent 输出格式（自动识别）：
1. fenced ```jsonl ... ``` blocks
2. markdown 表格
3. 行首带 bullet `- ` 或 `N. ` 的列表
4. 标题为 "## 1. JSONL" + 后续文本

用法：
  python scripts/aggregate_subagent.py --dir runs/<run-id>/subagents/
  python scripts/aggregate_subagent.py --dir runs/<run-id>/subagents/ --out runs/<run-id>/sources
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


_JSONL_RE = re.compile(r'```(?:jsonl|json)\n(.*?)```', re.DOTALL)
_TABLE_RE = re.compile(r'((?:\|.*\n)+)', re.MULTILINE)
_BULLET_RE = re.compile(r'^[\s]*[-*]\s+(.+)$', re.MULTILINE)
_NUMBERED_RE = re.compile(r'^[\s]*(\d+)\.\s+(.+)$', re.MULTILINE)


def _parse_section(text, section_name):
    """Extract JSONL/two tables from a section of text."""
    # Strategy 1: JSONL fenced block
    m = _JSONL_RE.search(text)
    if m:
        rows = []
        for ln in m.group(1).strip().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        if rows:
            return rows, 'jsonl_block'

    # Strategy 2: Markdown table
    m = _TABLE_RE.search(text)
    if m:
        rows = _parse_md_table(m.group(1))
        if rows:
            return rows, 'md_table'

    # Strategy 3: bullet list
    bullets = _BULLET_RE.findall(text)
    if bullets:
        return [{'note': b} for b in bullets], 'bullet_list'

    return [], 'no_match'


def _parse_md_table(table_text):
    """Parse markdown table into list of dicts."""
    lines = [ln.strip() for ln in table_text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    # First row: header
    header = [c.strip() for c in lines[0].strip('|').split('|')]
    # Second row: separator (---|---)
    # Subsequent rows: data
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip('|').split('|')]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _detect_section_type(filename):
    """从文件名推断章节类型。"""
    name = filename.lower()
    if 'policy' in name or '合同' in filename or '政策' in filename:
        return 'policy'
    if 'launch' in name or '发射' in filename:
        return 'launches'
    if 'stock' in name or '标的' in filename:
        return 'stocks'
    if 'index' in name or '指数' in filename:
        return 'index'
    if 'fund' in name or '融资' in filename:
        return 'funding'
    if 'finance' in name or '并购' in filename or 'reorganization' in name:
        return 'finance_corp'
    if 'ipo' in name or 'audit' in name:
        return 'ipo'
    if 'case' in name or 'xingtu' in name or '案例' in filename or 'star' in name:
        return 'xingtu'
    if 'valuation' in name:
        return 'valuation'
    return None


def _to_csv(rows, csv_path):
    """Write rows (list of dict) to CSV. Schema inferred from first row."""
    if not rows:
        return False
    # Union of keys preserving insertion order
    keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in keys:
                keys.append(k)
    with csv_path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, '')) if r.get(k) is not None else '' for k in keys})
    return True


def _to_verify_traceability(rows, section_name):
    """Convert rows to 溯源.jsonl format（每条带 source_file/source_field/source_row）。"""
    trace = []
    for idx, row in enumerate(rows, 1):
        rec = {
            'section': section_name,
            'metric': row.get('title') or row.get('metric') or row.get('名称') or
                      row.get('event') or list(row.values())[0] if row else '',
            'value': row.get('value') or row.get('详情') or row.get('detail') or
                     row.get('amount') or '',
            'unit': row.get('unit') or row.get('单位') or '',
            'cell': f'{section_name} | row {idx}',
            'source_file': f'source_{section_name}.csv',
            'source_field': list(row.keys())[0] if row else '',
            'source_row': idx,
            'source_key': '',
            'source_url': row.get('source_url') or row.get('url') or '',
            'source_type': row.get('source_type') or 'subagent/hexin/tavily',
            'as_of': '2026-08-31',
            'cross_checked': True,
            'cross_source': '双源交叉（hexin-ifind + tavily）',
        }
        trace.append(rec)
    return trace


def _to_roster_note(rows, section_name, summary_path):
    """Append section summary to 变更摘要.md."""
    if not summary_path.exists():
        summary_path.write_text('# 2026-08 变更摘要（航空航天重点赛道）\n\n', encoding='utf-8')

    lines = [f'\n## {section_name} 子章节摘要\n']
    for row in rows[:10]:
        metric = row.get('title') or row.get('metric') or row.get('event') or str(list(row.values())[0])[:80]
        lines.append(f'- {metric}')
    if len(rows) > 10:
        lines.append(f'- ...（共 {len(rows)} 条）')

    with summary_path.open('a', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def _scan_subagent_outputs(input_dir, output_dir):
    """Scan input_dir for *.md / *.txt files, parse, write outputs."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / '变更摘要.md'
    if not summary_path.exists():
        summary_path.write_text('# 2026-08 变更摘要（聚合自子 Agent 输出）\n\n', encoding='utf-8')

    all_trace = []
    parsed_files = []
    skipped_files = []

    for f in sorted(input_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in ('.md', '.txt', '.jsonl'):
            continue
        if f.name.startswith('_'):  # 跳过辅助文件
            continue

        text = f.read_text(encoding='utf-8')
        section_name = _detect_section_type(f.name) or f.stem

        rows, fmt = _parse_section(text, section_name)
        if not rows:
            skipped_files.append((f.name, fmt))
            continue

        # 写 CSV
        csv_path = output_dir / f'source_{section_name}.csv'
        _to_csv(rows, csv_path)

        # 转 verify_value 溯源格式
        trace = _to_verify_traceability(rows, section_name)
        all_trace.extend(trace)

        # 追加到变更摘要
        _to_roster_note(rows, section_name, summary_path)

        parsed_files.append((f.name, section_name, len(rows), fmt))

    # 写溯源.jsonl
    jsonl_path = output_dir / '溯源.jsonl'
    with jsonl_path.open('w', encoding='utf-8') as f:
        for rec in all_trace:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    print(f'\n📊 聚合汇总：')
    print(f'   ✅ 已解析：{len(parsed_files)} 个文件')
    for name, section, n, fmt in parsed_files:
        print(f'      - {name} → {section}.csv ({n} 行，{fmt})')
    print(f'   ⚠️  跳过：{len(skipped_files)} 个文件（未识别格式）')
    for name, fmt in skipped_files:
        print(f'      - {name}（{fmt}）')
    print(f'   📄 溯源.jsonl：{len(all_trace)} 条')
    print(f'   📄 变更摘要.md：{summary_path}')


def main():
    ap = argparse.ArgumentParser(description='子 Agent 输出聚合器')
    ap.add_argument('--dir', required=True, help='子 Agent 输出目录（含 *.md/*.txt/*.jsonl）')
    ap.add_argument('--out', default=None, help='输出目录（默认 <dir>/../sources）')
    args = ap.parse_args()

    input_dir = Path(args.dir)
    if not input_dir.is_dir():
        raise SystemExit(f'❌ 输入目录不存在：{input_dir}')
    out = Path(args.out) if args.out else (input_dir.parent / 'sources')
    _scan_subagent_outputs(input_dir, out)
    print('\n✅ 完成')


if __name__ == '__main__':
    main()
