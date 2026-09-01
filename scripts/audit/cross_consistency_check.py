# -*- coding: utf-8 -*-
"""
cross_consistency_check.py —— ⑤ 交叉一致性门禁（v3：全量纲汇总断言 + 加总等式）

v3 修复（2026-08 期事故驱动，评审报告 🔴#1/#2）：
  1. v2 只有 4 种模式（共/合计/总计 N 家、共 N 笔），导致「载荷 31 颗」「商业航天 12 笔」
     「19+3+9=31」全部漏抓 → claim=0 → 误判 ✅。v3 扩展为：
       A. 带触发词的计数断言（共/合计/总计/达/约/新增/移除/其中 …）× 全量纲
          （家/笔/颗/个/次/只/项/单/条/起/架/型/款/轮/座/枚/宗/场/份/名/人/批/台/发）
       B. 无触发词但属强计数单位（笔/颗/次/单/起/轮/架/宗/发），且段落含统计语境词
       C. 「N+M+K=L」加总等式：校验等式本身，并把 L 与候选表行数比对
  2. claim=0 时 v2 判 ✅。v3 判 SKIPPED（exit 2）并在报告首行标注「⚠️ 门禁未生效」——
     未提取到断言 ≠ 通过，必须显式可见并转盲审人工接管。
  3. 表格定位：claim 段落前后各 2 张表的窗口内找「数据行数最接近」者；
     兼容双行表头（首两行文本高度相似视为 2 行表头，修复旧 docx IPO 表 false positive）。

退出码：
  0 = 所有断言与候选表一致
  1 = 存在硬伤（断言与所有候选表行数差 ≥2，或加总等式不成立）
  2 = SKIPPED（未提取到任何汇总断言 / docx 不存在）——⚠️ 门禁未生效，非通过
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError as e:
    raise SystemExit('❌ python-docx 未安装：pip install python-docx') from e

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# ---- 计数单位（v3 全量纲；刻意排除 亿/万/%/元 等金额量纲，避免把金额当计数）----
_UNITS = (r'家|笔|颗|个|次|只|项|单|条|起|架|型|款|轮|座|枚|宗|场|份|名|人|批|台|发|例|席')
# 模式 A：带触发词（允许“约/达”弱断言，可容差更大）
_RE_CLAIM_STRONG = re.compile(r'(?:共|合计|总计|累计|新增|移除|其中|分别为?)\s*(\d+)\s*(%s)' % _UNITS)
_RE_CLAIM_SOFT = re.compile(r'(?:达|约|近|超|逾|累计(?:完成|达成)?)\s*(\d+)\s*(%s)' % _UNITS)
# 模式 B：无触发词 + 强计数单位，段落需含统计语境
_RE_CLAIM_BARE = re.compile(r'(\d+)\s*(笔|颗|次|单|起|轮|架|宗|发)')
_CONTEXT_WORDS = ('统计', '汇总', '合计', '分布', '构成', '发射', '融资', '交易', '事件', '并购', '中标', '载荷')
# 模式 C：加总等式 N+M+K=L
_RE_SUM_EQ = re.compile(r'(\d+)\s*[+＋]\s*((?:\d+\s*[+＋]\s*)*\d+)\s*[=＝]\s*(\d+)')

# 单元格文本归一（比对表头相似度用）
def _cell_texts(tr):
    out = []
    for tc in tr.findall(W + 'tc'):
        out.append(re.sub(r'\s+', '', ''.join((t.text or '') for t in tc.iter(W + 't'))))
    return out


def _data_rows(tbl):
    """数据行数 = tr 总数 - 表头行数（首两行文本相似判 2 行表头）。"""
    trs = tbl.findall(W + 'tr')
    if not trs:
        return 0, 0
    header = 1
    if len(trs) >= 2:
        a, b = _cell_texts(trs[0]), _cell_texts(trs[1])
        sa, sb = ''.join(a), ''.join(b)
        if sa and sb and (sa in sb or sb in sa or
                          difflib.SequenceMatcher(None, sa, sb).ratio() > 0.8):
            header = 2
    return max(0, len(trs) - header), header


def _para_text(p):
    return ''.join(r.text or '' for r in p.runs)


def _is_in_table(p, body):
    el = p._element
    cur = el.getparent()
    while cur is not None:
        if cur is body:
            break
        if cur.tag.endswith('}tbl'):
            return True
        cur = cur.getparent()
    return False


def _nearest_tables(body_children, idx, window=2):
    """返回 idx 段落前后 window 张表的 (position, tbl) 列表（按距离升序）。"""
    tbl_pos = [i for i, c in enumerate(body_children) if c.tag.endswith('}tbl')]
    ranked = sorted(tbl_pos, key=lambda t: abs(t - idx))
    return [(t, body_children[t]) for t in ranked[:window * 2]]


def _tbl_no(body_children, pos):
    """children 索引 → 人类可读表序号（第几张表）。"""
    if pos is None:
        return None
    return sum(1 for c in body_children[:pos] if c.tag.endswith('}tbl')) + 1


def _match_tables(claim_n, cands, soft=False):
    """在候选表里找与 claim 最接近者。返回 (verdict, best_rows, best_tbl_idx)。
    verdict: ok / off_by_one / mismatch / no_table"""
    best = None
    for pos, tbl in cands:
        n, _hdr = _data_rows(tbl)
        if n <= 0:
            continue
        diff = abs(n - claim_n)
        if best is None or diff < best[0]:
            best = (diff, n, pos)
    if best is None:
        return 'no_table', None, None
    diff, n, pos = best
    if diff == 0:
        return 'ok', n, pos
    if diff == 1:
        return 'off_by_one', n, pos
    if soft and diff <= 3:
        return 'off_by_one', n, pos  # 约/达类弱断言容差 3
    return 'mismatch', n, pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('--out', default='05_cross_consistency.md')
    args = ap.parse_args()

    if not Path(args.docx).exists():
        Path(args.out).write_text(
            '# 交叉一致性报告（cross_consistency_check.py v3）\n\n'
            '新月报不存在（%s）——门禁 SKIPPED。\n' % args.docx, encoding='utf-8')
        print('⚠️  交叉一致性：SKIPPED（新月报不存在）')
        sys.exit(2)

    doc = Document(args.docx)
    body = doc.element.body
    body_children = list(body.iterchildren())

    claims = []   # (para_element, index_in_body, n, snippet, soft)
    hard = []
    warn = []
    eq_checks = []

    for idx, child in enumerate(body_children):
        if not child.tag.endswith('}p'):
            continue
        from docx.text.paragraph import Paragraph
        p = Paragraph(child, doc)
        if _is_in_table(p, body):
            continue
        text = _para_text(p)
        if not text.strip():
            continue
        cands = _nearest_tables(body_children, idx)
        # 模式 A/B：计数断言
        seen_spans = []
        is_grouping = any(w in text for w in ('划分', '按', '其中', '分布'))  # 分组小计叙述（如「按发射场划分…2 次」「子赛道分布…12 笔」）
        unit_claims = {}  # 同段落分组求和校验：单位 -> [(n, span)]
        for pat, soft in ((_RE_CLAIM_STRONG, False), (_RE_CLAIM_SOFT, True)):
            for m in pat.finditer(text):
                span = m.span()
                if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
                    continue
                # 型号数字排除（如「长征七号 A Y16」的 16 是型号线不是计数）
                if span[0] > 0 and text[span[0] - 1] in 'Yy':
                    continue
                seen_spans.append(span)
                n = int(m.group(1))
                snippet = text[max(0, m.start() - 20):m.end() + 10].strip()
                unit_soft = soft
                unit = m.group(2)
                claims.append((n, snippet, unit_soft or is_grouping, idx))
                if unit in ('笔', '家', '单', '项') or is_grouping:
                    unit_claims.setdefault(unit, []).append((n, snippet))
                verdict, rows, pos = _match_tables(n, cands, soft=unit_soft)
                tbl_no = _tbl_no(body_children, pos)
                msg = '正文「%s」断言 %d，最近表(第%s张)数据行=%s' % (
                    snippet[:60], n, tbl_no if tbl_no else '无', rows)
                if verdict == 'ok':
                    continue
                if verdict in ('off_by_one', 'no_table'):
                    warn.append(msg + ('（无候选表，请人工确认）' if verdict == 'no_table' else '（差 1，疑似表头/口径差 1）'))
                elif unit_soft or is_grouping:
                    # 弱断言（约/达/超/累计）与分组小计：与整表行数不对应是常态 → 警告不阻断
                    warn.append(msg + ('（弱断言/分组叙述，不做表格硬比对，请人工确认）'))
                else:
                    hard.append(msg + '（差 ≥2）')
        # 模式 B：无触发词强单位 + 语境
        if any(w in text for w in _CONTEXT_WORDS):
            for m in _RE_CLAIM_BARE.finditer(text):
                span = m.span()
                if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
                    continue
                if span[0] > 0 and text[span[0] - 1] in 'Yy':
                    continue
                seen_spans.append(span)
                n = int(m.group(1))
                unit = m.group(2)
                snippet = text[max(0, m.start() - 20):m.end() + 10].strip()
                claims.append((n, snippet, is_grouping, idx))
                if unit in ('笔', '家', '单', '项') or is_grouping:
                    unit_claims.setdefault(unit, []).append((n, snippet))
                verdict, rows, pos = _match_tables(n, cands)
                tbl_no = _tbl_no(body_children, pos)
                msg = '正文「%s」断言 %d，最近表(第%s张)数据行=%s' % (
                    snippet[:60], n, tbl_no if tbl_no else '无', rows)
                if verdict == 'ok':
                    continue
                if verdict in ('off_by_one', 'no_table'):
                    warn.append(msg + ('（无候选表，请人工确认）' if verdict == 'no_table' else '（差 1）'))
                elif is_grouping:
                    warn.append(msg + '（分组小计叙述，请人工确认子类计数）')
                else:
                    hard.append(msg + '（差 ≥2）')
        # 模式 C 之前：分组求和校验——同段落内同单位断言 ≥2 时，Σ 与候选表行数比对
        # （抓「商业航天 12+卫星测控 2+低空 1+…=17 笔 vs 表 15 行」这类分布-表格矛盾）
        for unit, items in unit_claims.items():
            if len(items) < 2:
                continue
            total = sum(n for n, _s in items)
            cands2 = _nearest_tables(body_children, idx)
            best = None
            for pos, tbl in cands2:
                n_data, _hdr = _data_rows(tbl)
                if n_data <= 0:
                    continue
                d = abs(n_data - total)
                if best is None or d < best[0]:
                    best = (d, n_data, pos)
            if best and best[0] >= 2:
                snippet = ' + '.join(str(n) for n, _s in items) + f'（{unit}，合计 {total}）'
                warn.append(f'分组求和不符：「{snippet[:70]}」与最近表(第{_tbl_no(body_children, best[2])}张)数据行={best[1]}（差 {best[0]}）——'
                            '须核对子赛道统计口径')

        # 模式 C：加总等式
        for m in _RE_SUM_EQ.finditer(text):
            lhs = [int(x) for x in re.findall(r'\d+', m.group(0))[:-1]]
            rhs = int(m.group(0).split('=')[-1].split('＝')[-1].strip())
            ok_eq = sum(lhs) == rhs
            snippet = m.group(0)
            eq_checks.append((snippet, sum(lhs), rhs, ok_eq))
            if not ok_eq:
                hard.append('加总等式不成立：「%s」（各分量和=%d ≠ 右侧=%d）' % (snippet, sum(lhs), rhs))
            else:
                verdict, rows, pos = _match_tables(rhs, cands)
                if verdict not in ('ok',):
                    warn_msg = '等式「%s」右侧 %d' % (snippet, rhs)
                    if verdict == 'mismatch':
                        hard.append(warn_msg + '，最近表(第%d张)数据行=%s（差 ≥2）' % ((pos + 1) if pos is not None else -1, rows))
                    elif verdict == 'no_table':
                        warn.append(warn_msg + '：附近无可比对表，请人工确认')

    n_claim = len(claims)
    lines = [
        '# 交叉一致性报告（cross_consistency_check.py v3）',
        '',
        '| 指标 | 值 |',
        '| --- | --- |',
        f'| 来源 | {args.docx} |',
        f'| 表格数 | {len(doc.tables)} |',
        f'| 提取到的汇总断言 | {n_claim} |',
        f'| 加总等式 | {len(eq_checks)} |',
        f'| ⚠️ 警告 | {len(warn)} |',
        f'| ❌ 硬伤 | {len(hard)} |',
        '',
    ]
    if n_claim == 0 and not eq_checks:
        lines.insert(1, '> **⚠️ 门禁未生效（claim=0）**：未从正文提取到任何汇总断言或加总等式。\n'
                        '> 这不是通过——汇总叙述与表格的一致性需盲审人工复核。\n')
        lines += ['## 说明', '- v3 已启用全量纲提取（家/笔/颗/次/单/起/轮/架/…）+ 加总等式校验；',
                  '- 若本期月报确无汇总叙述，可由盲审确认后人工放行。']
    else:
        if claims:
            lines += ['## 断言明细', '| 断言值 | 上下文 |', '| --- | --- |']
            for n, snippet, soft, _idx in claims:
                lines.append(f'| {n}{"（弱）" if soft else ""} | {snippet[:70]} |')
        if eq_checks:
            lines += ['', '## 加总等式明细', '| 等式 | 分量和 | 右侧 | 判定 |', '| --- | --- | --- | --- |']
            for snippet, s, r, ok in eq_checks:
                lines.append(f'| {snippet} | {s} | {r} | {"✅" if ok else "❌"} |')
        if warn:
            lines += ['', f'## ⚠️ 警告：{len(warn)} 项', '']
            lines += [f'- {w}' for w in warn]
        if hard:
            lines += ['', f'## ❌ 硬伤：{len(hard)} 项', '']
            lines += [f'- {h}' for h in hard]
        else:
            lines += ['', '## ✅ 所有断言与候选表一致']

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')

    if n_claim == 0 and not eq_checks:
        print('⚠️  交叉一致性：SKIPPED（claim=0，门禁未生效）→ exit 2')
        sys.exit(2)
    if hard:
        print(f'❌ 交叉一致性：{len(hard)} 项硬伤，{len(warn)} 项警告（{args.out}）')
        sys.exit(1)
    print(f'✅ 交叉一致性：{n_claim} 项断言 + {len(eq_checks)} 等式通过，{len(warn)} 项警告（{args.out}）')


if __name__ == '__main__':
    main()
