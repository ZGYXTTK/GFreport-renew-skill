---
name: gfreport-renew-skill
description: "广发证券行业月报端到端生成（开源版）：以上期月报 docx 为模板，按月重采数据、保留格式改写、11 道门禁校验（数值真·docx 回读/空值 diff/一致性/交叉一致性/合理性/格式结构差/溯源反查/内容新鲜度/跨月去重，全门禁哈希绑定交付物指纹）、强制镜像到当前对话工作区。通用引擎 + 行业包（pack）机制，换行业只换 packs/<行业>/。内置 config JSON schema 校验、断点续跑、工作区多源探测（DSH Harness / Claude Code / 通用 CLI）、跨月复用配置（口径/采集/权威源/时点/标的池/端点）。子 Agent 通道失败由 mainagent 兜底并标注独立性受损。触发词：行业月报更新 / 月报更新 / 生成最新月报 / 更新月报 / 广发月报 / 重新生成月报 / generate monthly report."
version: "0.2.0"
author: gfreport-renew-skill-builder
license: Apache-2.0
activation: /gfreport-renew-skill
metadata:
  category: report-generation
  audience: sell-side-equity-research / industry-analyst
  scope: monthly-industry-report
  author: gfreport-renew-skill-builder
  version: 0.2.0
  created: 2026-08-31
  last_reviewed: 2026-09-01
  review_interval_days: 60
  requires_filesystem: true
  requires_network: true
  mcp_dependencies:
    - mx-ds-mcp
    - hexin-ifind-ds
    - qcc
    - itjuzi
    - qcc-document
    - qcc-tender
    - tavily-search
  python_packages:
    - python-docx>=0.8.11
    - requests>=2.31
    - jsonschema>=4.20
    - pandas>=2.0
    - xlrd==1.2.0
    - openpyxl>=3.1
  dependencies:
    - name: openxmlformats.org
      kind: namespace
      url: https://schemas.openxmlformats.org/
      note: OOXML XML 命名空间 URI（format_diff.py 中作为 XML namespace 字符串使用，非网络请求）
  schema_expectations: []
  external_endpoints:
    - "https://query.sse.com.cn/"
    - "https://www.szse.cn/"
    - "https://www.bse.cn/"
    - "http://eid.csrc.gov.cn/"
    - "https://www1.hkexnews.hk/"
    - "http://www.cninfo.com.cn/"
provenance:
  maintainer: gfreport-renew-skill-builder
  created: 2026-08-31
  source_references:
    - "原 industry-report-update Skill（v2.1）—— 本 Skill 是其按 Agent Skills Open Standard 完整重构的产物"
  audit_run_id: pending
  repository: "https://github.com/ZGYXTTK/GFreport-renew-skill"
  docs:
    - "docs/USAGE.md（使用说明：每月 SOP / 门禁速查 / 故障排查）"
    - "docs/EXAMPLES.md（修改示例：新增行业包 / 采集项 / 门禁 / 端点）"
---

# gfreport-renew-skill · 广发行业月报端到端更新

> 用一句话：以**上期月报 docx + 一份配置** 为输入，按月重采数据、按 9 道门禁校验后输出**结构保真**的新月报到当前工作区。
> 触发：`/gfreport-renew-skill` 或触发词「行业月报更新 / 月报更新 / 生成最新月报 / 更新月报 / 广发月报 / 重新生成月报」。

## 5 条铁律（v0.1.0 重构）

1. **数据流审计**：旧月报 = 结构模板 + 口径参考。**绝不**沿用数值。时点型按月全量重采；半结构型只核变化字段；结构型直接复制。
2. **格式保真（强制）**：Run `python scripts/build_report_v2.py --old old.docx --new new.docx --mapping mapping.json`（基于 `docx_utils.set_para_text_keep_fmt`）就地改写。**禁止** `Document() + add_paragraph + add_table` 从零生成。**禁止** `cell.text = value` 覆写。`format_diff` 相似度 ≥ 95% 是硬门槛（内容重建模式可用 `--soft-gates` 显式降级），未达即视为未交付。
3. **输入宽容**：旧月报可能是 docx / PDF / 混合。**优先 docx**；如只有 PDF，先 Run `python scripts/pdf_to_docx.py --pdf old.pdf --out new.docx`（5 级降级策略）转 docx，再用 build_report_v2.py 改写。
4. **工具盘点先于标 ✅**：所有 MCP / HTTP 通道必须先 smoke test 实测一次，未实测**只能**标 🟡。
5. **门禁不通过 = 未交付**：11 道门禁任一硬失败 → 返工（内容重建模式可用 `--soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff` 显式降级，降级记录 ⚠️ 转盲审）；`archive_to_workspace.py` 未执行 → 视为未交付。**哈希绑定**：每道门禁执行时记录 old/new docx SHA-256，校验对象 ≠ 交付对象直接判失败。
6. **跨行业只换包**：`packs/<行业>/RULES.md` 写行业专属纪律；通用纪律在本 SKILL.md。换行业不修改主入口。新建行业包 Run `python scripts/pack_wizard.py --name <行业>` 向导。
7. **run-id 复用**：默认每次跑新建 run-id。若配合 `--resume`，优先复用 `runs/{ym}-fixed/`（永久 run-id），避免新月报找不到。

## 资源索引（每行 `Run` 表示执行、`Read` 表示阅读）

| 类型 | 路径 | 动作 |
| --- | --- | --- |
| 编排入口 | `scripts/run_pipeline.py` | **Run** `python scripts/run_pipeline.py --old <旧.docx> --ym <YYYY-MM>` |
| 月报生成（v2 保真版） | `scripts/build_report_v2.py` | **Run** `python scripts/build_report_v2.py --old old.docx --new new.docx --mapping mapping.json` |
| PDF→docx 多策略 | `scripts/pdf_to_docx.py` | **Run** `python scripts/pdf_to_docx.py --pdf old.pdf --out new.docx` |
| 子任务聚合 | `scripts/aggregate_subagent.py` | **Run** `python scripts/aggregate_subagent.py --dir runs/<run-id>/subagents/` |
| 行业包向导 | `scripts/pack_wizard.py` | **Run** `python scripts/pack_wizard.py --name <行业>` |
| 通道实测自动回写 | `scripts/auto_smoke.py` | **Run** `python scripts/auto_smoke.py --run-id <run-id>` |
| 数据采集 | `scripts/collect.py` | **Run**（按 config/采集清单.json 自动调度） |
| 01 数字提取 | `scripts/audit/extract_numbers.py` | **Run**（run_pipeline 自动串联） |
| 02 配置校验 | `scripts/audit/config_check.py` | **Run**（run_pipeline 自动串联） |
| 03 空值 diff | `scripts/audit/diff_empty.py` | **Run**（run_pipeline 自动串联；`--soft-gates` 可降级） |
| 04 一致性 | `scripts/audit/consistency_check.py` | **Run**（run_pipeline 自动串联） |
| 05 交叉一致性 | `scripts/audit/cross_consistency_check.py` | **Run**（run_pipeline 自动串联；全量纲断言+分组求和+加总等式） |
| 06 合理性 | `scripts/audit/reasonableness_check.py` | **Run**（run_pipeline 自动串联；`--soft-gates` 可降级） |
| 07 格式对比 | `scripts/audit/format_diff.py` | **Run**（run_pipeline 自动串联；结构差清单+媒体计数+自比检测；`--format-struct-strict` 可硬阻断） |
| 08 数值回读 | `scripts/audit/verify_value.py` | **Run**（run_pipeline 自动串联；**真·docx 回读**：metric 关键词定位 docx 行 + CSV 双侧比对） |
| 09 溯源反查 | `scripts/audit/traceability_check.py` | **Run**（run_pipeline 自动串联） |
| 10 内容新鲜度 | `scripts/audit/content_freshness.py` | **Run**（run_pipeline 自动串联；防旧文残留冒充新月报） |
| 11 跨月去重 | `scripts/audit/dedupe_check.py` | **Run**（run_pipeline 自动串联；同主体同轮次指纹比对 + 无名主体拦截） |
| 格式保真 | `scripts/docx_utils.py` | **Read** 改写接口契约 |
| 通道自检 | `scripts/channel_health.py` | **Run** `python scripts/channel_health.py --ym <YYYY-MM> --run-id <run-id>` |
| 工作区探测 | `scripts/workspace.py` | **Read** detect_workspace 优先级 |
| 工作区归档 | `scripts/archive_to_workspace.py` | **Run**（run_pipeline 自动调用；不通过 = 未交付） |
| 行业包 | `packs/<行业>/` | **Read** RULES.md + 复写 config/* |
| 激活配置 | `config/*.json` | **Read**（JSON schema 见 `config/_schemas/`）|
| 通道端点 | `config/endpoints.json` | **Read** 官网改接口只改这里 |
| 工具注册表 | `config/tool_registry.json` | **Read** Step 2 必须覆盖 |
| 模板 | `templates/` | **Read** 任务/确认/变更/溯源 schema |
| 评估 | `evals/gfreport-renew.eval.md` + `scripts/run_evals.py` | **Run** `python scripts/run_evals.py --rollout` |
| 决策契约 | `discovery.json` | **Read** marketplace 检索依据 |
| 已知坑 | `references/gotchas.md` | **Read** |
| 使用说明 | `docs/USAGE.md` | **Read** 每月 SOP / 门禁速查 / 故障排查 / 命令参考 |
| 修改示例 | `docs/EXAMPLES.md` | **Read** 新增行业包 / 采集项 / 门禁 / 端点的完整示例 |

## 10 步闭环（run_pipeline.py 已串好，单命令执行）

| 步 | 动作 | 承载 | 提示 |
| --- | --- | --- | --- |
| 0 | 数据流审计 | `scripts/audit/extract_numbers.py` | **Run**（run_pipeline 自动） |
| 0.5 | 通道健康度 | `scripts/channel_health.py` | **Run** `python scripts/channel_health.py --ym <YYYY-MM> --run-id <run-id>` |
| 1 | 章节拆解 + 口径快照 | `scripts/snapshot.py` | **Run**（run_pipeline 自动） |
| 2 | 工具盘点 | `scripts/tool_inventory.py` | **Run**（run_pipeline 自动） |
| 3 | 能力汇总 | （run_pipeline 内联） | — |
| 4 | 一次性确认 | `templates/确认清单.md` | **Read** |
| 5 | 数据采集 | `scripts/collect.py` + 6 个 subagent（policy/launches/IPO/finance/funding/case） + `scripts/aggregate_subagent.py`（聚合输出） | **Run**（Agent 调 MCP/子 Agent） |
| 5.5 | 映射 + 就地改写 | `scripts/build_report_v2.py`（基于 7 月 docx 复制 + docx_utils） | **Run** `python scripts/build_report_v2.py --old old.docx --new new.docx --mapping mapping.json --verify-format` |
| 6 | 9 道门禁 | `scripts/audit/*.py` | **Run**（run_pipeline 自动串联；中断续跑 `python scripts/run_pipeline.py --old <旧.docx> --ym <YYYY-MM> --resume`） |
| 7 | 来源归档 | `scripts/audit/verify_value.py` | **Run**（run_pipeline 自动） |
| 8 | 独立盲审 | `templates/subagent_任务.md` 第六节 | **Run**（子 Agent 调） |
| 9 | 归档 + 度量 | `scripts/metrics.py` | **Run**（run_pipeline 自动） |
| 9.5 | 工作区镜像 | `scripts/archive_to_workspace.py` | **Run**（run_pipeline 自动；P0-11 强制） |

## 跨月复用配置（每月仅改「截至日期」）

| 文件 | 用途 | 动作 |
| --- | --- | --- |
| `config/endpoints.json` | 10 个 HTTP + 9 个 MCP + 2 个 agent 通道 | **Read**（通道名匹配见下） |
| `config/tool_registry.json` | 11 类已知信息源（含 kind=registry 必须 discover） | **Read**（Step 2 必覆盖） |
| `config/采集清单.json` | 时点型/半结构型/结构型 + 枚举 + 输出 | **Read**（每月改"截至日期"） |
| `config/权威源映射.json` | 字段维度权威源 + 通用降级 + 冲突处理 | **Read**（冲突消解用） |
| `config/口径字典.json` | 字段命名/统计窗口/币种/单位 | **Read**（统一字段口径） |
| `config/时点对齐.json` | 各源数据时点 → 目标时点 | **Read**（跨源对齐用） |
| `config/标的池.json` | 赛道白名单（半结构型只核变化用） | **Read**（半结构型核变化用） |
| `config/_schemas/*.schema.json` | 每个 JSON 的 schema（jsonschema 校验） | **Read**（schema 强校验用） |

新增字段先改 schema，再改值。YAML 已被 JSON 取代。

## 关键纪律（**Read** `references/discipline.md` 看完整 P0/P1/P2 三级纪律）

**P0 阻断级**（违反即返工）：
- 拿不到 → 标「本期无法获取 / —」，禁止编造
- 时点型必须按月重采完整枚举
- 未实测通道不得标 ✅
- 月报数字 = 源文件数字（`verify_value` 无 ❌）
- 格式对齐 ≥95%（`format_diff`）
- `archive_to_workspace` 必须执行，缺失即视为未交付
- 盲审通过；复审必须换新审核 Agent

**P1 警告级**：必填 ≤5 条确认 / 字段口径一致 / 时点统一 / 财报期双轨 / 差距如实报告 / 通道降级可追溯 / 每表对应章节+具体来源 / 归档完整。

**P2 行业包级**：见 `packs/<行业>/RULES.md`。

## Gotchas（**Read** `references/gotchas.md` 查看完整 12 条避坑手册）

| # | 坑 | 怎么避 |
| --- | --- | --- |
| 1 | 旧月报 docx 含 `<w:hyperlink>` 的 run 改写会留旧文字 | `docx_utils._set_run_text` 已处理，**禁止**自行 `cell.text =` |
| 2 | 跨行 vMerge 复杂表头门禁识别不到 | 落"未知结构"标记，由盲审人工复核 |
| 3 | 数字 + 单位字符串"1亿元"≠"1万元"（同数字误判通过） | `verify_value._UNITS` 按"币种+数量级"最长匹配 |
| 4 | 港股 IPO 6 个月未聆讯 = 失效条目，不能"基线-变化"高估 | robotics 行业包 RULES.md 规则1 |
| 5 | 招股书 PDF 不可获取填「未取得招股书」 | 禁止 "以招股书为准" 占位（专题 .skill 同源纪律）|
| 6 | 原生 OOXML 图表门禁无法重算 | 双轨制：保留原图 + 图下脚注 + 数据表列为必更新项 |
| 7 | 上交所/深交所官网 WAF / SSL 异常 | 走 `mx-ds-mcp` / `iFinD` 降级；CSRC 必须 http 非 https |
| 8 | 子公司 vs 集团合并口径混用 | `口径字典.json` 中 `法人统一工商名` 强制规则 |
| 9 | subagent 通道连续失败 ≥3 次 | 暂停执行，提示人工检查模型路由 |
| 10 | 工作区探测退化为 cwd 即触发 `_inside_base` 守卫 | 自动拒写入，要求显式 `--ws` 或 `--anchor` |
| 11 | 「Y16」型号线数字会被交叉一致性排除 | 火箭型号线不是计数断言，`Y\d+` 自动跳过 |
| 12 | 内容重建模式下 03/06/07 必然失败（结构重构是预期） | `run_pipeline.py --soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff` 显式降级；降级失败转盲审人工复核 |

## 已知边界（如实声明，不伪装）

1. `format_diff` 是 rPr/pPr/gridSpan 签名比对，不覆盖图表视觉差异；含图表报告需人工复核。
2. 门禁查"自洽 + 回读一致"，无法发现源文件本身的错误；权威源选择靠 Step 2 映射纪律。
3. `diff_empty` / `verify_value` 的键归一化是启发式；极端同名异写需人工复核（落入盲审）。
4. subagent 通道失败 ≥3 次必须暂停，不允许主 Agent 静默接管后无标注。
5. 工作区镜像只确保"产物在用户指定位置"，不保证运行环境内有编辑工具（用户需自行打开）。

---

## 安装与执行

### 安装（任何 harness / 编辑器通用）

```bash
# 方式 1：Tier-1 工具（Claude Code / Cursor / Gemini / Kiro / Goose / OpenCode / Cline / Roo / Kilo / Factory / Antigravity / Codex CLI）
bash install.sh         # Linux/macOS
pwsh -File install.ps1   # Windows
# 安装器自动链接到 12 个 Tier-1 工具 + 通用 ~/.agents/skills/ 兜底

# 方式 2：Claude Code 通过 marketplace
# 先把仓库上传到 GitHub，然后 /plugin marketplace add <owner>/<repo>

# Tier 2/3 工具（Windsurf / Trae / Junie / Zed / Augment / Aider / Continue.dev）
# v0.2.0 补；v0.1.0 未声明兼容
```

### 一次性执行

```bash
python scripts/run_pipeline.py --old "<旧月报.docx>" --ym 2026-08
# 中断后续跑
python scripts/run_pipeline.py --old "<旧月报.docx>" --ym 2026-08 --resume
# 指定工作区（推荐）
python scripts/run_pipeline.py --old "<旧月报.docx>" --ym 2026-08 --ws "D:\\工作区"
# 用输入旧月报所在目录反推工作区（open-source 通用）
python scripts/run_pipeline.py --old "<旧月报.docx>" --ym 2026-08 --anchor "<旧月报.docx>"
```

### 评估（防回归）

```bash
python scripts/run_evals.py --rollout
```

---

## 子 Skill（专题对比）

专题对比（双公司深度对比）走独立子 Skill `专题研究.skill/`，前置从 `runs/<run-id>/manifest.json` 读取契约。
本 Skill 主入口**不**实现专题，避免单次专题占 50%+ token。

---

## 评估 / 修订记录

- v0.1.0 (2026-08-31)：初版。按 `/agent-skill-creator` 审计报告与行业月报 v2.1 设计思路完整重构。