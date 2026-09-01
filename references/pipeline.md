# 10 步 Pipeline 详解

> SKILL.md 主流程的展开版。`scripts/run_pipeline.py` 已实现自动串联。
> 这里说明每一步的"目的 + 输出 + 失败处置"。

## Step 0 · 数据流审计（铁律 1）

- **目的**：反推每个旧月报结论性数字的数据源 / 口径 / 时点
- **脚本**：`scripts/audit/extract_numbers.py`
- **输入**：旧月报 docx
- **输出**：`runs/<run-id>/logs/01_extract_numbers.md`（不阻断）
- **失败处置**：从不阻断（产出清单供后续 Step 2 / 5 / 7 引用）

## Step 0.5 · 通道健康度

- **目的**：HTTP 直探 + MCP/agent 实测回写校验
- **脚本**：`scripts/channel_health.py`
- **输入**：--ym --run-id
- **输出**：`runs/<run-id>/通道健康度-<ym>.md` + 追加 `state/渠道历史.jsonl`
- **失败处置**：HTTP ❌ → 后续采集按 `config/权威源映射.json` 降级链走；MCP 🟡 → Agent 立即实测一次并回写 `sources/通道实测.jsonl`；连续 ❌ ≥2 期 → 提示"续费/改接口"

## Step 1 · config 校验 + snapshot + manifest init

- **目的**：把"跨月复用配置"在运行开始前校验一遍
- **脚本**：`scripts/audit/config_check.py` + `scripts/snapshot.py snapshot` + `scripts/manifest.py init`
- **输入**：--ym --run-id --pack
- **输出**：`runs/<run-id>/logs/02_config_check.md` + `config/口径快照/<ym>.json` + `runs/<run-id>/manifest.json`
- **失败处置**：config_check ❌ → exit 1（采集清单含未声明通道名）；snapshot 写入失败 → WARN（不阻断）；manifest init 已存在 → WARN（不覆盖）

## Step 2 · 工具盘点（两段式枚举 + 机检）

- **目的**：穷尽本机全部可用信息源
- **脚本**：`scripts/tool_inventory.py`（机检）+ Agent 写 `工具清单.jsonl`
- **输入**：`runs/<run-id>/sources/工具清单.jsonl`
- **输出**：`runs/<run-id>/logs/工具清单校验报告.md`
- **失败处置**：阻断（缺聚合器探查 / 注册表内源未盘点 / 未测标 ✅）

## Step 3 · 能力汇总

- 由 run_pipeline 内联：打印 ❌/🟡/✅ 列表（不阻断）

## Step 4 · 一次性确认

- **模板**：`templates/确认清单.md`（5 条必填 + 4 条建议项）
- **失败处置**：未确认 → Agent 暂停请求用户

## Step 5 · 副本修改生成

- **脚本**：`scripts/collect.py plan` + Agent 调 MCP/子 Agent 执行
- **输入**：`config/采集清单.json` + `packs/<行业>/config/`
- **输出**：`runs/<run-id>/download/*.csv` + `download/采集计划.jsonl`
- **失败处置**：单个采集项失败 → 按降级链切换；所有降级都失败 → 标 "本期无法获取"

## Step 5.5 · docx 改写

- **脚本**：`scripts/docx_utils.py`（库）
- **强制**：`cell.text = value` ❌；必须 `set_cell_text_keep_fmt` / `add_row_copy_fmt` / `set_para_segments_keep_fmt`
- **失败处置**：任何 `cell.text=` 改写被审查到 → 触发 P0-8（格式对齐不通过）

## Step 6 · 11 道门禁（run_pipeline 跑）

- 见 SKILL.md 门禁速查表
- v0.2.0：新增 10 content_freshness（防旧文残留）与 11 dedupe_check（跨月去重/无名主体）；
  全部门禁哈希绑定——每道门禁记录所验 docx 的 SHA-256，与交付物指纹不一致即硬失败
- 内容重建模式：`--soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff` 显式降级（⚠️ 转盲审）
- 中断续跑：`--resume` 跳过已通过且指纹未变的门禁（state 在 `runs/<run-id>/gate_state.json`；指纹变了强制重跑）
- 最多 3 轮，第 3 轮仍失败 → 报告用户

## Step 7 · 溯源 + 数值回读

- **脚本**：`scripts/audit/verify_value.py`（v0.2.0：`--docx` 真·docx 回读——溯源 metric 关键词定位 docx 行，校验值真的写在交付文档里；弱校验模式 exit 2 不计通过）+ `scripts/audit/traceability_check.py`
- **输入**：溯源.jsonl + 源 CSV + 新月报 docx
- **输出**：`runs/<run-id>/logs/08_verify_value.md` + `runs/<run-id>/logs/09_traceability.md`
- **失败处置**：❌ → 修正溯源.jsonl 锚点 / 补源文件；"幽灵条目"（docx 中无该行）→ 补写正文或删溯源

## Step 8 · 独立盲审

- **脚本**：`templates/subagent_任务.md` 第六节（盲审规范）
- **输入**：新月报 docx + `download/` 源文件 + `sources/` 通道实测
- **输出**：`runs/<run-id>/reviews/独立审核意见.md`
- **失败处置**：阻断级 >0 → 回 Step 5/6 修正 + **换新审核 Agent 复审**；子 Agent 通道失败 ≥2 次 → 降级 mainagent 并标注「独立性受损」

## Step 9 · 归档 + 度量

- **脚本**：`scripts/metrics.py record`
- **输入**：--ym --run-id --gates='extract=0,config=0,...'
- **输出**：`runs/metrics.json`（跨月累加）
- **失败处置**：metrics 写入失败 → WARN（不阻断）

## Step 9.5 · 工作区镜像（P0-11 · 强制收尾）

- **脚本**：`scripts/pipeline_gate.py`（P0 守卫）+ `scripts/archive_to_workspace.py`（实际镜像）
- **输入**：--run-id --ws/--anchor --product
- **输出**：`<工作区>/<产品>_产出/{根, 输入, 源文件, 门禁报告, SUMMARY.md}`
- **失败处置**：P0 守卫失败 → exit 1；_inside_base 守卫 → exit（拒绝写入 skill 基目录）；写入异常 → SystemExit

## 运行示例

```bash
# 第一次跑
python scripts/run_pipeline.py --old ./7月.docx --ym 2026-08 --ws D:\\工作区

# Agent 在 prompt 里跑 Step 5/8（采集 + docx 改写 + 盲审），完成后：
python scripts/run_pipeline.py --old ./7月.docx --ym 2026-08 --ws D:\\工作区 --resume
# → 自动跑 extract/config_check/channel_health/collect_plan/snapshot + 9 道门禁 + archive
```