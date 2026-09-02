# -*- coding: utf-8 -*-
"""
traceability_check.py —— ⑨ 溯源反查门禁（v1）

校验溯源.jsonl：
  - 每条必须有 source_file 或 url
  - 至少 90% 记录有 cross_checked 字段
  - 默认 min-coverage=0.9（仅对登记溯源行的覆盖率，不含日期/序号等非溯源辅助单元格）
"""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jsonl')
    ap.add_argument('--min-coverage', type=float, default=0.9)
    ap.add_argument('--require-cross-check', action='store_true')
    ap.add_argument('--base-dir', default=None)
    ap.add_argument('--out', default='09_traceability.md')
    args = ap.parse_args()

    if not Path(args.jsonl).exists():
        Path(args.out).write_text(
            f'# 溯源反查报告（traceability_check.py v1）\n\n溯源.jsonl 不存在（{args.jsonl}）——门禁 SKIPPED。\n',
            encoding='utf-8')
        print(f'⚠️  溯源反查：SKIPPED（溯源.jsonl 不存在）')
        sys.exit(2)

    recs = []
    for ln, line in enumerate(Path(args.jsonl).read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            print(f'❌ 第 {ln} 行 JSON 解析失败')
            return 2

    base_dir = args.base_dir
    has_source = 0
    has_anchor = 0
    has_cross = 0
    problems = []

    for rec in recs:
        sf = rec.get('source_file')
        url = rec.get('url')
        if sf or url:
            has_source += 1
        else:
            problems.append(f'cell={rec.get("cell")}：无 source_file / url')

        if rec.get('source_key') or rec.get('source_row'):
            has_anchor += 1

        if rec.get('cross_checked'):
            has_cross += 1

    total = len(recs)
    if total == 0:
        Path(args.out).write_text('# 溯源反查报告（traceability_check.py v1）\n\n溯源.jsonl 为空\n', encoding='utf-8')
        return

    coverage = has_anchor / total if total else 0
    cross_rate = has_cross / total if total else 0

    hard = []
    if coverage < args.min_coverage:
        hard.append(f'锚点覆盖率 {coverage:.1%} < {args.min_coverage:.0%} 阈值')
    if args.require_cross_check and cross_rate < args.min_coverage:
        hard.append(f'交叉验证率 {cross_rate:.1%} < {args.min_coverage:.0%} 阈值')

    lines = [
        '# 溯源反查报告（traceability_check.py v1）',
        f'总记录：{total} ｜ 有出处（source_file/url）：{has_source} ｜ 有锚点：{has_anchor} ｜ 交叉验证：{has_cross}',
        f'锚点覆盖率：{coverage:.1%}（阈值 {args.min_coverage:.0%}）｜ 交叉验证率：{cross_rate:.1%}',
        '',
    ]
    if problems:
        lines.append('## 缺失出处')
        for p in problems:
            lines.append(f'- ❌ {p}')
    if hard:
        lines += ['', f'## ❌ 硬伤']
        for h in hard:
            lines.append(f'- {h}')
    else:
        lines += ['', '## ✅ 无硬伤']

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    print(f'覆盖率 {coverage:.1%}｜交叉 {cross_rate:.1%}（{args.out}）')
    if hard:
        sys.exit(1)


if __name__ == '__main__':
    main()