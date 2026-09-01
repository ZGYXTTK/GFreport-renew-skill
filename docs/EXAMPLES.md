# 修改示例（EXAMPLES）

> gfreport-renew-skill v0.2.0 · 面向**维护者/扩展者**。使用方法见 [docs/USAGE.md](USAGE.md)。
> 每个示例 = 目标 / 改哪里 / 完整示例 / 如何验证。改配置前先读 `references/discipline.md`（P0 纪律）。

---

## 示例 1：新增一个行业包（以 robotics 为例）

**目标**：让流水线支持"机器人行业月报"。

**第 1 步 · 用向导生成骨架**（Run）：

```bash
python scripts/pack_wizard.py --name robotics
```

**第 2 步 · 写行业纪律** `packs/robotics/RULES.md`（必须覆盖 6 条默认纪律）：

```markdown
# robotics 行业包（机器人与具身智能）

## 行业专属纪律（覆盖 _default 的 6 条默认纪律）
1. 数据时点：截至自然月月末。
2. 来源时效：二级市场行情 ≤1 天；IPO/再融资 ≤7 天；产业政策 ≤30 天。
3. 缺失处理：拿不到标「本期无法获取 / —」，禁止"约/估计"占位。
4. 币种一致：默认 CNY；海外标的（Figure/Boston Dynamics）保留原币种并注汇率来源。
5. 跨期可比：环比 ±20% 须在变更摘要点名；人形机器人出货量、融资笔数为高敏感指标。
6. 结构型字段：封面/目录/表格列结构直接复制不重采。

## 行业专属规则
- 港股 IPO 6 个月未聆讯 = 失效条目，不得计入"在审"（历史事故规则，见 Gotchas #3）。
- "人形机器人/工业机器人/服务机器人"按标的池 sub_industry 字段区分，禁止混计。
```

**第 3 步 · 复写配置**：把 `packs/_default/config/*.json` 拷到 `packs/robotics/config/`，逐个改：

```jsonc
// packs/robotics/config/标的池.json —— 至少 1 家（否则 extract_numbers 找不到业务键）
{
  "version": "1.0",
  "companies": [
    { "公司简称": "埃斯顿", "法人统一工商名": "埃斯顿自动化股份有限公司", "sub_industry": "工业机器人" },
    { "公司简称": "宇树科技", "法人统一工商名": "杭州宇树科技有限公司", "sub_industry": "人形机器人" }
  ]
}
```

**第 4 步 · 配月度关键词** `packs/robotics/config/新鲜度关键词.json`：

```json
{
  "2026-09": ["宇树科技", "人形机器人", "Figure", "特斯拉Optimus", "2026-09-30"],
  "default": ["IPO", "融资", "机器人", "具身智能"]
}
```

**第 5 步 · 运行 + 验证**：

```bash
python scripts/run_pipeline.py --old ./机器人7月.docx --ym 2026-09 --pack robotics --ws "D:\工作区"
# 验证：config_check 门禁（02）通过 = 新包 schema 全部合法
```

---

## 示例 2：新增一个采集项

**目标**：本期新增"科创板做市商扩容名单"采集。

**改** `config/采集清单.json`（或行业包同名文件）：

```jsonc
{
  "items": [
    // ...原有项...
    {
      "id": "科创板做市商扩容",           // 全局唯一
      "类型": "半结构型",                 // 时点型=全量重采 / 半结构型=只核变化 / 结构型=直接复制
      "通道": ["mcp__mx-ds-mcp__mx_ashare_finance_data", "mcp__tavily-search__tavily_search"],
      //      ↑ 通道名必须逐字存在于 config/endpoints.json（02 门禁强校验）
      "口径": "上交所公告披露口径",
      "枚举": "拉全量做市商列表 → 对比上期 → 只列新增/退出",
      "输出": "上交所公告-科创板做市商.csv"
    }
  ]
}
```

**验证**：重跑 `02_config_check` 门禁——通道名不认识会 ❌，字段类型不符会 ❌（schema 强校验：`config/_schemas/采集清单.schema.json`）。

---

## 示例 3：更新月度新鲜度关键词

**目标**：让 10 号门禁按 9 月词表验"新瓶装新酒"。

**改** `packs/aerospace/config/新鲜度关键词.json`：

```json
{
  "2026-09": ["蓝箭航天", "天龙三号", "千帆星座", "低空经济促进法", "2026-09-30"],
  "default": ["C919", "商业航天", "低空经济", "IPO", "融资"]
}
```

**验证**：`python scripts/audit/content_freshness.py 新月报.docx --ym 2026-09 --pack aerospace --old 上期.docx`
——词表未配置时门禁退化为 2 条泛化词并在报告头标注「泛化模式」（此时门禁可信度低，需盲审补位）。

---

## 示例 4：修改 / 新增 HTTP 数据源

**目标**：巨潮资讯改版后更新端点；新增一个公告聚合端点。

**改** `config/endpoints.json`：

```jsonc
{
  "http": [
    // ...原有 10 个...
    {
      "name": "巨潮资讯公告检索",                       // 采集清单引用这个名字
      "url": "http://www.cninfo.com.cn/new/hisAnnouncement/query",
      "method": "POST",
      "kind": "json",
      "headers": { "User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded" },
      "body": { "pageNum": "1", "pageSize": "30", "column": "szse" },
      "note": "翻页用 pageNum；WAF 需 UA"
    }
  ]
}
```

**同步两处**（缺一不可）：
1. `SKILL.md` frontmatter 的 `external_endpoints` 增加域名（安全扫描按它核对未声明端点）；
2. `discovery.json` → `risk.permissions` 的端点数描述。

**验证**：`python scripts/channel_health.py --ym <本期> --run-id smoke` 该通道应 ✅；然后在 `采集清单.json` 引用新通道名跑 02 门禁。

---

## 示例 5：调整门禁阈值

**场景 A · 格式阈值放宽**（老模板扫描件转换后相似度天然低）：

```bash
python scripts/run_pipeline.py ... --format-threshold 0.90
```

**场景 B · 新鲜度更严**：

```bash
python scripts/run_pipeline.py ... --freshness-threshold 0.7
```

**场景 C · 跨月去重金额容差**：改 `scripts/audit/dedupe_check.py` 默认值或在 evals 中透传：

```python
ap.add_argument('--amount-tol', type=float, default=0.2)  # 0.2=20%，改为 0.1 更严
```

**原则**：阈值属于"交付口径"，调整须记录在 `变更摘要.md` 或 CHANGELOG，不允许跑批时临时改。

---

## 示例 6：新增一道门禁

**目标**：加"12 号门禁：正文不得出现运维信息（如『余额不足』『通道实测』字样）"——2026-08 期真实事故（P125 混入运维信息）。

**第 1 步 · 写脚本** `scripts/audit/ops_leak_check.py`：

```python
# -*- coding: utf-8 -*-
"""12 ops_leak_check —— 正文运维信息泄漏检查。exit: 0=干净 1=有泄漏 2=SKIPPED"""
import re, sys
from pathlib import Path
try:
    from docx import Document
except ImportError:
    raise SystemExit('❌ python-docx 未安装')

PATTERNS = [r'余额不足', r'通道实测', r'API\s*[Kk]ey', r'run[- ]id[=:]?\s*\d{8}', r'mcp__\w+__\w+']

def main():
    ap_r = sys.argv[1]
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else '12_ops_leak.md'
    doc = Document(ap_r)
    texts = [p.text for p in doc.paragraphs] + \
            [c.text for t in doc.tables for r in t.rows for c in r.cells]
    hits = [(i, s, pat) for i, s in enumerate(texts) for pat in PATTERNS
            if re.search(pat, s or '')]
    lines = ['# 运维信息泄漏报告（12）', f'命中：{len(hits)}'] + \
            [f'- 段{i}：{s[:60]}（匹配 {pat}）' for i, s, pat in hits[:30]]
    Path(out).write_text('\n'.join(lines), encoding='utf-8')
    print(f'运维信息泄漏：{len(hits)} 处（{out}）')
    sys.exit(1 if hits else 0)

if __name__ == '__main__':
    main()
```

**第 2 步 · 注册进编排**（`scripts/run_pipeline.py` 两处）：

```python
# GATE_OUTPUTS 字典加：
    '12_ops_leak_check': '12_ops_leak.md',
# HARD_GATES 元组加：
    ..., '11_dedupe_check', '12_ops_leak_check')
# new_docx.exists() 块里，仿照 11 号门禁加调用：
    if not _should_skip(state, '12_ops_leak_check', args, new_sha=new_sha):
        code = _run([str(_AUDIT / 'ops_leak_check.py'), str(new_docx),
                     '--out', str(run_dir / 'logs' / GATE_OUTPUTS['12_ops_leak_check'])],
                    '12_ops_leak_check')
        _record(state, '12_ops_leak_check', code, new_sha=new_sha)
```

**第 3 步 · 同步文档**：SKILL.md / AGENTS.md / README 门禁表 + discovery.json `success_measure` 门禁数。
**第 4 步 · 验证**：fixtures 冒烟 + 真实期跑一遍（新门禁 exit 0/1/2 都要见到才算覆盖）。

---

## 示例 7：扩展交叉一致性的断言模式

**目标**：行业里出现新量纲（如"架次"）要纳入正文-表格一致性校验。

**改** `scripts/audit/cross_consistency_check.py`：

```python
# _UNITS 交替串加入新单位（排除金额量纲 亿/万/%/元）
_UNITS = (r'家|笔|颗|个|次|只|项|单|条|起|架|型|款|轮|座|枚|宗|场|份|名|人|批|台|发|例|席|架次')
# 强计数单位（无触发词也要抓的）：
_RE_CLAIM_BARE = re.compile(r'(\d+)\s*(笔|颗|次|单|起|轮|架|宗|发|架次)')
```

**验证**：`python scripts/audit/cross_consistency_check.py 新月报.docx --out test.md`——先看断言明细有没有把正常叙述误抓（误抓→从强计数单位移回 _UNITS）；再对历史事故报告跑一遍确认能抓到。

---

## 示例 8：格式保真改写（生成器侧的最小调用）

**目标**：不用完整 pipeline，只做"旧 docx → 新 docx 保真改字"。

```python
# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, 'scripts')
from docx import Document
from docx_utils import set_para_text_keep_fmt, set_cell_text_keep_fmt

mapping = [{"match": "7月", "replace": "8月", "scope": "paragraph"}]
doc = Document('旧.docx')                    # 注意：先 shutil.copy2 复制底稿再改，别动原件
for p in doc.paragraphs:
    t = ''.join(r.text or '' for r in p.runs)
    for rule in mapping:
        if rule['scope'] != 'cell' and rule['match'] in t:
            set_para_text_keep_fmt(p, t.replace(rule['match'], rule['replace']))
doc.save('新.docx')
```

**三条铁律**：①先复制后改写；②永远走 `docx_utils`（自动处理超链接内 run、多 run 格式克隆）；③改完立刻跑 `format_diff` + `content_freshness` 自检。禁止 `cell.text = value`（会留下超链接旧文字并毁格式）。

---

## 附：修改后的标准验证流程

```bash
# 1. 语法
python -c "import ast; ast.parse(open('scripts/改动文件.py',encoding='utf-8').read())"
# 2. 配置 schema（若改了 config/*.json）
python scripts/audit/config_check.py --run-id schema-test
# 3. 冒烟（正负双向）
python evals/cases/make_fixtures.py && python scripts/run_evals.py --rollout
# 4. 官方门禁
python <agent-skill-creator>/scripts/validate.py . && \
python <agent-skill-creator>/scripts/security_scan.py .
# 5. 真实期（有当月数据时）：全门禁 + 盲审，然后 CHANGELOG 记一笔
```
