# -*- coding: utf-8 -*-
"""
consistency_check.py —— ④ 一致性门禁（v1）

检查含「合计/总计/小计」关键字的行 = 各分项之和。
依赖：python-docx
"""
import argparse
import re
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError as e:
    raise SystemExit('❌ python-docx 未安装') from e

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_NUM = re.compile(r'-?\d+(?:\.\d+)?')
_TOTAL_KEYS = ('合计', '总计', '小计', '合  计', '总  计')


def _parse_num(s):
    if not s:
        return None
    m = _NUM.search(str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(',', ''))
    except ValueError:
        return None


def _is_total(text):
    return any(k in text for k in _TOTAL_KEYS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('--rel-tol', type=float, default=0.001)
    ap.add_argument('--out', default='04_consistency.md')
    args = ap.parse_args()

    if not Path(args.docx).exists():
        Path(args.out).write_text(
            f'# 一致性报告（consistency_check.py v1）\n\n新月报不存在（{args.docx}）——门禁 SKIPPED。\n',
            encoding='utf-8')
        print(f'⚠️  一致性：SKIPPED（新月报不存在）')
        sys.exit(2)

    doc = Document(args.docx)
    hard = []

    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            # 找合计/总计行：首列是关键字，其余列是数字
            if not _is_total(cells[0]):
                continue
            nums = [_parse_num(c) for c in cells[1:]]
            nums = [n for n in nums if n is not None]
            if len(nums) < 2:
                continue
            s = sum(nums)
            if not nums[:-1]:
                continue
            # 假设最后一列是合计
            total = nums[-1]
            partial = sum(nums[:-1])
            denom = max(abs(total), abs(partial), 1.0)
            if abs(total - partial) > args.rel_tol * denom:
                hard.append(f'表{ti}.行{ri}：首列「{cells[0]}」 → 合计={total} 分项和={partial}')

    lines = [
        '# 一致性校验报告（consistency_check.py v1）',
        f'来源：{args.docx} ｜ 相对误差容忍：{args.rel_tol}',
        '',
    ]
    if hard:
        lines.append(f'## ❌ 硬伤：{len(hard)} 项')
        for h in hard:
            lines.append(f'- {h}')
    else:
        lines.append('## ✅ 无硬伤（所有合计行 = 分项和）')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')

    if hard:
        print(f'❌ 一致性：{len(hard)} 项硬伤（{args.out}）')
        sys.exit(1)
    print(f'✅ 一致性：无硬伤（{args.out}）')


if __name__ == '__main__':
    main()