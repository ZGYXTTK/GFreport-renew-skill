# -*- coding: utf-8 -*-
"""
format_diff.py —— ⑦ 格式对比门禁（v2：结构差清单 + 媒体计数 + 自比检测）

v2 修复（2026-08 期事故驱动，评审报告 🔴#1、🟡#12）：
  1. v1 把所有表格 token 化为 ('tbl',)，19 表 vs 13 表也能被 SequenceMatcher 错位对齐，
     在「图片 10→0、表 19→13、列结构全变」时仍报「相似度 100%」。v2 表 token 携带
     （行数, 首行单元格数, 首格文本签名），形状不同的表不再被错误对齐。
  2. v1 明确跳过 drawing/pict 子树 → 媒体对象全删也测不出。v2 独立统计
     word/media/ 文件数与 document.xml 内 drawing/pict 计数，差异写入结构差清单。
  3. 自比检测：old/new SHA-256 相同 → 直接判失败（2026-08 期 04/06/07 疑似跑在
     旧 run 中间稿上的教训：校验对象 ≠ 交付对象必须在此处暴露）。
  4. --struct-strict：结构差（表数/图片数/媒体计数变化）非零即判失败；默认仅醒目标注。

退出码：
  0 = 相似度 ≥ 阈值且（未开 strict 或无结构差）
  1 = 相似度 < 阈值，或自比，或 strict 下存在结构差
  2 = SKIPPED（新月报不存在）
"""
import argparse
import difflib
import hashlib
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

SKIP_TAGS = {'drawing', 'pict', 'blip', 'imagedata', 'AlternateContent', 'Fallback',
             'object', 'OLEObject', 'shape', 'group', 'fldData', 'binData'}
SKIP_ATTRS = {'id', 'embed', 'link', 'relid', 'paraId', 'textId', 'gfxdata', 'uid',
              'durableId', 'w14:textId', 'w14:paraId'}


def _local(tag):
    return tag.split('}')[-1]


def _text(el):
    return ''.join((t.text or '') for t in el.iter(W + 't'))


def _norm(s):
    return re.sub(r'\d+', '#', (s or '').strip())


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _media_count(path):
    with zipfile.ZipFile(path) as z:
        return sum(1 for n in z.namelist() if n.startswith('word/media/'))


def _drawing_count(root):
    return sum(1 for el in root.iter() if _local(el.tag) in ('drawing', 'pict'))


def _tbl_shape(tbl):
    """(行数, 首行单元格数, 首格归一文本) —— 表 token 的辨识三元组。"""
    trs = tbl.findall(W + 'tr')
    n_rows = len(trs)
    first_cells = trs[0].findall(W + 'tc') if trs else []
    n_cols = len(first_cells)
    head = _norm(_text(first_cells[0]))[:24] if first_cells else ''
    return (n_rows, n_cols, head)


def _is_binary(v):
    return v is not None and len(v) > 200


def _skip_subtree(el):
    return _local(el.tag) in SKIP_TAGS


def _diff_fmt(el_a, el_b, path, diffs):
    compared = matched = 0
    ta, tb = _local(el_a.tag), _local(el_b.tag)
    if ta != tb:
        diffs.append((path, 'tag', ta, tb))
        return 0, 0
    attrs_a = {k.split('}')[-1]: v for k, v in el_a.attrib.items()}
    attrs_b = {k.split('}')[-1]: v for k, v in el_b.attrib.items()}
    for k in sorted(set(attrs_a) | set(attrs_b)):
        va, vb = attrs_a.get(k), attrs_b.get(k)
        if k in SKIP_ATTRS or (_is_binary(va) or _is_binary(vb)):
            continue
        compared += 1
        if va == vb:
            matched += 1
        else:
            diffs.append((path, 'attr:' + k, str(va), str(vb)))
    children_a = [c for c in el_a if _local(c.tag) != 't' and not _skip_subtree(c)]
    children_b = [c for c in el_b if _local(c.tag) != 't' and not _skip_subtree(c)]
    for i in range(min(len(children_a), len(children_b))):
        c, m = _diff_fmt(children_a[i], children_b[i],
                         f'{path}/{_local(children_a[i].tag)}[{i}]', diffs)
        compared += c
        matched += m
    if len(children_a) != len(children_b):
        compared += 1
        diffs.append((path, 'children-count', str(len(children_a)), str(len(children_b))))
    return compared, matched


def _para_token(p):
    return ('p', _norm(_text(p)))


def _tbl_token(tbl):
    n_rows, n_cols, head = _tbl_shape(tbl)
    return ('tbl', n_rows, n_cols, head)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('old_docx')
    ap.add_argument('new_docx')
    ap.add_argument('--threshold', type=float, default=0.95)
    ap.add_argument('--struct-strict', action='store_true',
                    help='结构差（表数/图片数/媒体数）非零即判失败')
    ap.add_argument('--out', default='07_format_diff.md')
    args = ap.parse_args()

    if not Path(args.new_docx).exists():
        Path(args.out).write_text(
            f'# 格式对比（format_diff.py v2）\n\n新月报未生成（{args.new_docx}）——门禁 SKIPPED。\n',
            encoding='utf-8')
        print('⚠️  格式对比：SKIPPED（新月报不存在）')
        sys.exit(2)

    # ---- 自比检测 ----
    sha_old, sha_new = _sha256(args.old_docx), _sha256(args.new_docx)
    self_compare = sha_old == sha_new

    with zipfile.ZipFile(args.old_docx) as z:
        old_root = ET.fromstring(z.read('word/document.xml'))
        old_media = sum(1 for n in z.namelist() if n.startswith('word/media/'))
    with zipfile.ZipFile(args.new_docx) as z:
        new_root = ET.fromstring(z.read('word/document.xml'))
        new_media = sum(1 for n in z.namelist() if n.startswith('word/media/'))
    old_body = old_root.find(W + 'body')
    new_body = new_root.find(W + 'body')
    old_blocks = [el for el in old_body if _local(el.tag) in ('p', 'tbl')] if old_body is not None else []
    new_blocks = [el for el in new_body if _local(el.tag) in ('p', 'tbl')] if new_body is not None else []

    old_tokens = [_para_token(b) if _local(b.tag) == 'p' else _tbl_token(b) for b in old_blocks]
    new_tokens = [_para_token(b) if _local(b.tag) == 'p' else _tbl_token(b) for b in new_blocks]

    old_tbls = [b for b in old_blocks if _local(b.tag) == 'tbl']
    new_tbls = [b for b in new_blocks if _local(b.tag) == 'tbl']
    old_draw = _drawing_count(old_root)
    new_draw = _drawing_count(new_root)

    compared = matched = 0
    diffs = []
    struct = []
    shape_diffs = []
    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for a, b in zip(range(i1, i2), range(j1, j2)):
                if _local(old_blocks[a].tag) == 'p':
                    c, m = _diff_fmt(old_blocks[a], new_blocks[b], f'段落{a}', diffs)
                else:
                    c, m = _diff_fmt(old_blocks[a], new_blocks[b], f'表{a}', diffs)
                    ra, ca, _ = _tbl_shape(old_blocks[a])
                    rb, cb, _ = _tbl_shape(new_blocks[b])
                    if (ra, ca) != (rb, cb):
                        shape_diffs.append(f'表{a}：{ra}行×{ca}列 → {rb}行×{cb}列')
                compared += c
                matched += m
        else:
            struct.append(f'{tag} 块（旧[{i1}:{i2}] → 新[{j1}:{j2}]）')

    # ---- 结构差清单 ----
    tbl_diff = len(new_tbls) - len(old_tbls)
    media_diff = new_media - old_media
    draw_diff = new_draw - old_draw
    if tbl_diff:
        struct.append(f'表格数量：{len(old_tbls)} → {len(new_tbls)}（{tbl_diff:+d}）')
    if media_diff:
        struct.append(f'内嵌图片（word/media）：{old_media} → {new_media}（{media_diff:+d}）')
    if draw_diff:
        struct.append(f'drawing/pict 元素：{old_draw} → {new_draw}（{draw_diff:+d}）')
    if shape_diffs:
        struct.append(f'配对表形状变化：{len(shape_diffs)} 张')
    struct_significant = bool(tbl_diff or media_diff or draw_diff)

    score = (matched / compared) if compared else 1.0
    passed = score >= args.threshold and not self_compare
    if args.struct_strict and struct_significant:
        passed = False

    lines = [
        '# 格式对比报告（format_diff.py v2）',
        '',
        '| 指标 | 值 |',
        '| --- | --- |',
        f'| 相似度评分 | {score * 100:.1f}% |',
        f'| 比对属性数 | {compared} |',
        f'| 匹配数 | {matched} |',
        f'| 结构变化块 | {len(struct)} 项 |',
        f'| 表格数量 | {len(old_tbls)} → {len(new_tbls)} |',
        f'| 内嵌图片（media） | {old_media} → {new_media} |',
        f'| drawing/pict 计数 | {old_draw} → {new_draw} |',
        f'| 配对表形状变化 | {len(shape_diffs)} 张 |',
        f'| 格式回归 | {len(diffs)} 项 |',
        f'| 自比检测 | {"❌ 两文档完全相同（校验对象≠交付对象！）" if self_compare else "✅ 正常（old≠new）"} |',
        f'| 阈值 | {args.threshold * 100:.0f}% |',
        f'| 结论 | {"✅ 通过" if passed else "❌ 未通过"} |',
    ]
    if struct_significant:
        lines.insert(2, '\n> **⚠️ 结构差显著**：表格/图片/媒体对象数量发生变化。相似度分数不反映结构退化，'
                        '请逐条核对下方结构差清单（模板保真的底线是媒体与表格不丢失）。')
    if shape_diffs:
        lines += ['', '## 配对表形状变化（不计分，但须人工确认）']
        lines += [f'- {s}' for s in shape_diffs[:30]]
    if struct:
        lines += ['', '## 结构变化块']
        lines += [f'- {s}' for s in struct[:30]]
    if diffs:
        lines += ['', '## 格式回归明细（前 50 条）']
        for d in diffs[:50]:
            lines.append(f'- {d[0]} {d[1]}：旧={d[2]} 新={d[3]}')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    print(f'相似度 {score * 100:.1f}%（阈值 {args.threshold * 100:.0f}%）→ {"通过" if passed else "未通过"}；'
          f'表 {len(old_tbls)}→{len(new_tbls)}，图 {old_media}→{new_media}，结构 {len(struct)} 项，回归 {len(diffs)} 项（{args.out}）')
    if self_compare:
        print('❌ 自比检测：old 与 new 为同一文档——门禁没有校验交付物本身！')
    if not passed:
        sys.exit(1)


if __name__ == '__main__':
    main()
