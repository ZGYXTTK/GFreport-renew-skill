# gfreport-renew-skill · Companion for Tools Reading AGENTS.md

> Codex CLI / Cursor / Kiro / Goose / Roo / Cline / Zed 等 15+ 工具优先读 AGENTS.md 而非 SKILL.md。
> 本文件是 SKILL.md 的精简入口，详细文档全部在 `SKILL.md` + `references/`。

## Purpose

Generate a sell-side monthly industry report from a prior docx + config files, with nine enforceable gates (numerical readback / empty-value diff / consistency / cross-consistency / reasonableness / format alignment ≥95% / source cross-check) and mandatory mirror to the user's current workspace.

## Activation Triggers

Use this skill when the user asks for any of:
- 行业月报更新 / 月报更新 / 生成最新月报 / 更新月报
- 广发月报 / 重新生成月报
- generate monthly report / update monthly industry report
- "把上期月报按最新数据重做一份"

Do **not** use this skill for: one-off research notes, daily/weekly briefs, special-topic deep-dive (use the sibling `专题研究.skill/`), or charts/spreadsheets without an existing prior report template.

## Inputs

| Name | Required | Description |
| --- | --- | --- |
| `--old` | yes | Path to the previous-month docx report |
| `--ym` | yes | Target month in `YYYY-MM` |
| `--ws` | optional | Absolute path to user's current workspace |
| `--anchor` | optional | File inside the user's workspace (defaults to `--old`'s directory) |
| `--resume` | optional | Skip already-passed gates (state in `<out-dir>/gate_state.json`) |
| `--pack` | optional | Industry pack name (default: `_default`) |

## Outputs

Written under `<workspace>/<product>_产出/`:
- `新月报_<YYYY-MM>.docx` — preserved-format new report
- `变更摘要.md` — what changed, abnormal movements, new/removed targets
- `源文件/` — raw CSVs / 溯源.jsonl / 通道实测.jsonl
- `门禁报告/` — 9 gate reports (gates named `01-09`)
- `SUMMARY.md` — single-file summary of all gate states

## Five Iron Rules (the soul of this skill)

1. **数据流审计** — prior report is *only* a structural template; never reuse numbers.
2. **格式保真** — use `scripts/docx_utils.py`; never `cell.text = value`.
3. **工具盘点先于 ✅** — every MCP/HTTP channel must be smoke-tested; untested = 🟡.
4. **门禁不通过 = 未交付** — any hard failure → rework; `archive_to_workspace.py` not run → not delivered.
5. **跨行业只换包** — `packs/<行业>/RULES.md` holds pack-specific rules; never edit main SKILL.md to change industries.

## Eleven Gates (executed in order by `run_pipeline.py`)

| # | Gate | Pass condition |
| --- | --- | --- |
| 01 | 数字提取 | extracts all claim-bearing numbers from old docx |
| 02 | 配置校验 | every 采集项 has required fields and known channel name |
| 03 | 空值 diff | no 旧有值 → 新空值 for aligned business keys (soft via `--soft-gates`) |
| 04 | 一致性 | 合计 = 分项和 |
| 05 | 交叉一致性 | summary claims match table row counts; sum equations hold; group-sum vs table rows |
| 06 | 合理性 | 环比 ±50% / new-removed targets all explained in 变更摘要.md (soft via `--soft-gates`) |
| 07 | 格式对比 | similarity ≥ 95% + structure-diff list (tables/media); self-compare = fail (soft via `--soft-gates`) |
| 08 | 数值回读 | every anchored 溯源 row reads back equal in source CSV **and exists in the delivered docx** |
| 09 | 溯源反查 | ≥ 90% coverage, every source has cross_checked entry |
| 10 | 内容新鲜度 | new report actually contains target-month content (≥50% keyword hits) |
| 11 | 跨月去重 | no same-entity-same-round contradictions; no anonymous entities |

All gates are hash-bound: each run records the SHA-256 of the old/new docx it verified;
a gate whose fingerprint differs from the delivered docx is a hard failure.

## Gotchas

1. Old docx with `<w:hyperlink>` runs — `docx_utils._set_run_text` handles it; never hand-roll `cell.text =`.
2. Currency "1亿美元" ≠ "1亿元" same number: `verify_value._UNITS` does longest-match on currency+magnitude.
3. SSE/SZSE official sites have WAF / SSL issues — fall back to `mx-ds-mcp` / `iFinD`; CSRC is **http** not https (SSL handshake fails on https).
4. Native OOXML charts not recomputable — keep image + footnote + update data table.
5. Hong Kong IPO entries expire after 6 months without hearing — flag, do not extrapolate.
6. Prospectus unavailable → mark 「未取得招股书」; never write "以招股书为准".
7. Workspace fallback to cwd triggers `_inside_base` guard → explicit `--ws` or `--anchor` required.
8. subagent channel fails 3× → pause, never silently fall back to main agent.

For full references, see `SKILL.md` and `references/` directory.