# _default 行业包（通用兜底）

> 适用于：未指定具体行业的通用月报模板，或作为新行业 pack 的最小可运行基线。
> 任何具体行业 pack 都应至少包含这 6 条；缺则视为"行业规则未声明"。

## 通用纪律（P2 级）

1. **数据时点**：默认目标时点为采集日所在自然月的月末（如 2026-08 月报 → 截至 2026-07-31）。例外须在 RULES.md 显式声明。
2. **来源时效**：所有数据采集前必须确认最近一次 `LAST_VERIFIED` 不超过 90 天；超期需先跑 `channel_health.py` + smoke test 再采。
3. **缺失处理**：拿不到的字段全部标 "本期无法获取 / —"，禁止编造。
4. **币种一致**：默认人民币（CNY）。港股 / 美股 字段需在 RULES.md 显式说明币种与汇率来源。
5. **跨期可比**：环比 ±20% 以上的字段必须在本期变更摘要.md 点名原因（默认比 P0 的 ±50% 阈值更严格）。
6. **结构型字段**：报告封面、目录、章节标题、表格列结构属于结构型，按 P0-1 直接复制，不重采。

## 激活方式

```bash
# 默认（无需指定）
python scripts/run_pipeline.py --old <old.docx> --ym 2026-08

# 显式
python scripts/run_pipeline.py --old <old.docx> --ym 2026-08 --pack _default
```

## 创建新行业包（pack）

1. `packs/<行业>/` 下复制 `_default` 的 6 个 JSON + RULES.md
2. 改 `config/采集清单.json`、`config/标的池.json`、`config/口径字典.json`
3. 在 `config/权威源映射.json` 增补字段专属权威源
4. 写 `packs/<行业>/RULES.md`（覆盖上面 6 条默认纪律 + 行业特化规则）
5. 跑 `python scripts/run_pipeline.py --pack <行业> --old <old.docx> --ym <ym>`

## 与 P0/P1 纪律的关系

本包**只**承接 SKILL.md 的 P2 层（行业专属）。通用 P0/P1 在 SKILL.md 主文件，**不**在本包内重述。