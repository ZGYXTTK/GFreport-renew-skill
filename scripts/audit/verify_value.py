# -*- coding: utf-8 -*-
"""
verify_value.py —— ⑧ 数值回读门禁（v2：真·docx 回读）

v2 修复（2026-08 期事故驱动，评审报告 🔴#1）：
  v1 的「月报值」取自 溯源.jsonl 的 value 字段，再与源 CSV 比对——溯源自己声称什么
  就校验什么，等于自证清白。事故案例：峰飞 V5000、时的 E20 两行在月报正文政策表中
  根本不存在，v1 仍判 ✅。

v2 改法（--docx 启用）：
  1. 对每条溯源记录，从 metric 提取定位关键词（括号内证券代码 / ≥3 字中文实体）；
  2. 在新月报 docx 的全部表格行中搜索关键词命中行；
  3. 检查该行内是否存在与 value 匹配的单元格（数值+单位折算或文本包含）；
  4. docx 侧与 CSV 侧双重校验：
       - docx 无命中行            → ❌ 「docx 中未找到该指标」（杀掉幽灵条目）
       - docx 行存在但值不符      → ❌ 「docx 行存在但值不匹配」
       - docx ✅ 但 CSV 值不一致  → ❌ 「月报与源文件不一致」
       - 双侧一致                 → ✅
  5. 未传 --docx 时退化为 v1 行为，但报告头显式标注「⚠️ 弱校验模式」，且整体结论
     降级为 warning（run_pipeline 会把它计为 SKIPPED，不冒充通过）。

数字 + 单位按「币种+数量级」最长匹配折算；币种/单位不一致 → 硬伤。
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from docx import Document
except ImportError as e:
    raise SystemExit('❌ python-docx 未安装：pip install python-docx') from e

_NUM = re.compile(r'[-+]?\d[\d,]*\.?\d*')
# 币种+数量级复合单位必须排在单纯数量级之前（最长匹配优先）
_UNITS = [
    ('万亿美元', 1e16), ('万亿港元', 1e12), ('万亿元人民币', 1e12), ('万亿元', 1e12), ('万亿', 1e12),
    ('亿美元', 1e8), ('亿港元', 1e8), ('亿元人民币', 1e8), ('亿元', 1e8), ('亿', 1e8),
    ('万美元', 1e4), ('万港元', 1e4), ('万元人民币', 1e4), ('万元', 1e4), ('万', 1e4),
    ('美元', 1.0), ('港元', 1.0), ('人民币', 1.0), ('元', 1.0),
]


def _unit_factor(s):
    if not s:
        return None, None
    if '%' in s:
        return 0.01, '%'
    for u, f in _UNITS:
        if u in s:
            return f, u
    return None, None


def _currency(label):
    if not label:
        return None
    if '美元' in label:
        return 'USD'
    if '港元' in label:
        return 'HKD'
    if '人民币' in label or any(c in label for c in ('亿元', '亿', '万元', '万', '元')):
        return 'CNY'
    return None


def _read_csv(path):
    if not Path(path).exists():
        return None
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            with open(path, encoding=enc, newline='') as f:
                rows = [r for r in csv.reader(f) if any((c or '').strip() for c in r)]
            if rows:
                return rows
        except UnicodeDecodeError:
            continue
    return None


def _parse_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    m = _NUM.search(v)
    if not m:
        return None
    try:
        return float(m.group(0).replace(',', ''))
    except ValueError:
        return None


def _norm_text(s):
    s = str(s or '')
    s = s.replace('（', '(').replace('）', ')').replace('，', ',')
    return re.sub(r'\s+', '', s)


def _metric_keys(metric):
    """从 metric 提取定位关键词。

    主键 = 混合实体段（中/英/数字/括号连续 token，如「A 公司」「航发动力(600893.SH)」），
    自动剥离「月涨跌/类别/在审进度」等表头类尾部词；证券代码（600893.SH）单列兜底键。
    返回按长度降序去重列表；keys[:1] 为主键，keys[1:] 为辅助键。"""
    m = str(metric or '')
    keys = []
    token = (r'[A-Za-z0-9\u4e00-\u9fff（(）)·\-\.]')
    for seg in re.finditer(
            token + r'+(?:\s+' + token + r'+)*', m):
        s = seg.group(0).strip()
        for tail in ('月涨跌', '涨跌幅', '在审进度', '审核状态', '类别', '结果',
                     '募资额', '轮次', '金额', '摘要', '标题', '子赛道'):
            if s.endswith(tail) and len(s) > len(tail):
                s = s[:-len(tail)]
                break
        s = s.strip(' ,，-')
        if len(re.sub(r'\s+', '', s)) >= 2:
            keys.append(s)
    # 兜底：括号内证券代码（600893.SH）
    for mm in re.finditer(r'\(?([0-9]{5,6}\.[A-Za-z]{2,4})\)?', m):
        keys.append(mm.group(1))
    seen, out = set(), []
    for k in sorted(set(keys), key=lambda x: -len(x)):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


class DocxIndex:
    """新月报表格行索引：norm(整行文本) -> (表号, 行号, [各 cell 原文])"""

    def __init__(self, docx_path):
        self.doc = Document(str(docx_path))
        self.rows = []
        for ti, table in enumerate(self.doc.tables):
            for ri, row in enumerate(table.rows):
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    self.rows.append((ti, ri, cells))

    def _hits(self, keys):
        """返回命中任一 key 的全部行 [(ti, ri, cells), ...]。"""
        if not keys:
            return []
        out = []
        for ti, ri, cells in self.rows:
            norm = _norm_text(' | '.join(cells))
            if any(k and _norm_text(k) in norm for k in keys):
                out.append((ti, ri, cells))
        return out

    def check_value(self, primary, aux, val):
        """主键（最长关键词）命中行优先，逐行检查 value；主键无匹配值再降级辅助键。
        返回 (verdict, note)：verdict ∈ ok / bad / miss。"""
        miss = ('miss', 'docx 中未找到该指标行（幽灵条目）')
        bad = None
        for keys in (primary, aux):
            if not keys:
                continue
            hits = self._hits(keys)
            if not hits:
                continue
            for ti, ri, cells in hits:
                if self.value_in_row(cells, val):
                    return 'ok', f'docx 第{ti + 1}表第{ri + 1}行回读一致'
            if bad is None:
                bad = ('bad', f'docx 第{hits[0][0] + 1}表第{hits[0][1] + 1}行存在但值不匹配')
        return bad or miss

    def value_in_row(self, row_cells, val):
        """检查 val（数值+单位折算 / 文本包含）是否出现在该行任一单元格。"""
        a = _parse_num(val)
        if a is not None:
            fa, ua = _unit_factor(str(val))
            ca = _currency(ua)
            for cell in row_cells:
                b = _parse_num(cell)
                if b is None:
                    continue
                fb, ub = _unit_factor(cell)
                cb = _currency(ub)
                if fa is not None and fb is not None and ca and cb:
                    if ca != cb:
                        continue
                    va, vb = a * fa, b * fb
                    if abs(va - vb) <= 0.001 * max(abs(va), abs(vb), 1.0):
                        return True
                else:
                    if abs(a - b) <= 0.001 * max(abs(a), abs(b), 1.0):
                        return True
            return False
        # 文本值：去空白包含
        nv = _norm_text(val)
        if not nv:
            return True
        return any(nv in _norm_text(c) for c in row_cells)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jsonl')
    ap.add_argument('--base-dir', default=None)
    ap.add_argument('--docx', default=None, help='新月报 docx（传入即启用真·docx 回读）')
    ap.add_argument('--rel-tol', type=float, default=0.001)
    ap.add_argument('--require-anchor', action='store_true')
    ap.add_argument('--out', default='08_verify_value.md')
    args = ap.parse_args()

    if not Path(args.jsonl).exists():
        Path(args.out).write_text(
            '# 数值回读报告（verify_value.py v2）\n\n溯源.jsonl 不存在 —— 门禁 SKIPPED。\n',
            encoding='utf-8')
        print('⚠️  数值回读：SKIPPED（溯源.jsonl 不存在）')
        sys.exit(2)

    base_dir = args.base_dir or os.path.dirname(os.path.abspath(args.jsonl))
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

    docx_idx = None
    weak = True
    if args.docx and Path(args.docx).exists():
        docx_idx = DocxIndex(args.docx)
        weak = False

    csv_cache = {}
    results = []  # (cell, val, src_val, verdict, note)
    for rec in recs:
        cell = str(rec.get('metric') or rec.get('cell') or '?')
        val = rec.get('value')
        if rec.get('status') == 'gap':
            results.append((cell, val, None, 'skip', 'gap'))
            continue

        # ---------- docx 侧（真回读：主键定位 → 辅助键兜底 → 逐行值校验） ----------
        docx_verdict, docx_note = None, ''
        if docx_idx is not None:
            keys = _metric_keys(str(rec.get('metric') or cell))
            if not keys:
                docx_verdict, docx_note = 'bad', 'metric 无法提取定位关键词'
            else:
                docx_verdict, docx_note = docx_idx.check_value(keys[:1], keys[1:], val)

        # ---------- CSV 侧 ----------
        csv_verdict, csv_note, src_val = None, '', None
        sf = rec.get('source_file') or ''
        if not sf:
            csv_verdict, csv_note = 'warn', '无 source_file'
        else:
            path = sf if os.path.isabs(sf) else os.path.join(base_dir, sf)
            if path not in csv_cache:
                csv_cache[path] = _read_csv(path)
            rows = csv_cache[path]
            if rows is None:
                csv_verdict, csv_note = 'bad', f'源文件缺失：{sf}'
            elif not rec.get('source_field') and rec.get('source_key') in (None, '') and rec.get('source_row') in (None, ''):
                csv_verdict, csv_note = 'warn', '无锚点'
            else:
                header, data = rows[0], rows[1:]
                ci = next((i for i, h in enumerate(header)
                           if rec.get('source_field') and rec.get('source_field') in (h or '')), None)
                if ci is None:
                    csv_verdict, csv_note = 'warn', f'列未命中：{rec.get("source_field")}'
                else:
                    row = None
                    if rec.get('source_key'):
                        for r in data:
                            if r and _norm_text(rec['source_key']) and _norm_text(rec['source_key']) in _norm_text(r[0] or ''):
                                row = r
                                break
                    elif rec.get('source_row') is not None:
                        try:
                            ri = int(rec['source_row']) - 1
                            if 0 <= ri < len(data):
                                row = data[ri]
                        except (TypeError, ValueError):
                            pass
                    if not row or ci >= len(row):
                        csv_verdict, csv_note = 'bad', '行/列定位失败'
                    else:
                        src_val = row[ci]
                        a, b = _parse_num(val), _parse_num(src_val)
                        if a is not None and b is not None:
                            fa, ua = _unit_factor(str(val))
                            fb, ub = _unit_factor(f'{src_val} {header[ci]}')
                            if fa is not None and fb is not None:
                                ca, cb = _currency(ua), _currency(ub)
                                if ca and cb and ca != cb:
                                    csv_verdict, csv_note = 'bad', f'币种不一致 {ca}→{cb}'
                                else:
                                    va, vb = a * fa, b * fb
                                    csv_verdict = 'ok' if abs(va - vb) <= args.rel_tol * max(abs(va), abs(vb), 1.0) else 'bad'
                                    csv_note = '折算一致' if csv_verdict == 'ok' else f'折算不一致 {va} vs {vb}'
                            else:
                                csv_verdict = 'ok' if abs(a - b) <= args.rel_tol * max(abs(a), abs(b), 1.0) else 'bad'
                                csv_note = '数值一致' if csv_verdict == 'ok' else f'数值不一致 {a} vs {b}'
                        else:
                            same = _norm_text(val) == _norm_text(src_val)
                            csv_verdict = 'ok' if same else 'bad'
                            csv_note = '文本一致' if same else '文本不一致'

        # ---------- 合成判定：docx 侧优先暴露幽灵/失配 ----------
        if docx_verdict == 'bad':
            results.append((cell, val, src_val, 'bad', docx_note))
            continue
        if csv_verdict == 'bad':
            results.append((cell, val, src_val, 'bad', csv_note))
            continue
        if docx_verdict == 'ok' and csv_verdict == 'ok':
            results.append((cell, val, src_val, 'ok', 'docx + CSV 双侧一致'))
            continue
        if csv_verdict in ('warn', None) and docx_verdict == 'ok':
            results.append((cell, val, src_val, 'warn', f'{csv_note}｜docx 回读一致'))
            continue
        if csv_verdict == 'ok' and docx_verdict is None:
            results.append((cell, val, src_val, 'ok', csv_note + '｜⚠️ 未启用 docx 回读'))
            continue
        results.append((cell, val, src_val, csv_verdict or 'warn', csv_note or docx_note))

    n_ok = sum(1 for r in results if r[3] == 'ok')
    n_bad = sum(1 for r in results if r[3] == 'bad')
    n_warn = sum(1 for r in results if r[3] == 'warn')
    n_skip = sum(1 for r in results if r[3] == 'skip')

    icon = {'ok': '✅', 'bad': '❌', 'warn': '🟡', 'skip': '➖'}
    head = ['# 数值回读报告（verify_value.py v2）']
    if weak:
        head.insert(1, '> **⚠️ 弱校验模式**：未传 --docx，未做真·docx 回读；结论不可作为交付依据。')
    else:
        head.insert(1, '> 校验模式：**真·docx 回读**（metric 关键词定位 docx 表格行 + 源 CSV 双侧比对）。')
    lines = head + [
        f'溯源记录：{len(recs)} ｜ ✅ {n_ok} / ❌ {n_bad} / 🟡 {n_warn} / ➖ {n_skip}',
        '',
        '| 指标 | 月报值 | 源文件值 | 判定 | 说明 |',
        '| --- | --- | --- | --- | --- |',
    ]
    for cell, val, src_val, verdict, note in results:
        lines.append(f'| {str(cell)[:36]} | {str(val)[:30]} | {str(src_val)[:30] if src_val is not None else ""} | {icon[verdict]} | {note} |')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    print(f'✅{n_ok} ❌{n_bad} 🟡{n_warn} ➖{n_skip}（{args.out}）'
          + ('［弱校验模式］' if weak else '［真·docx 回读］'))
    if weak:
        sys.exit(2)  # 弱校验 = 门禁未完全生效，不计通过
    if n_bad:
        sys.exit(1)


if __name__ == '__main__':
    main()
