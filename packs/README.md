# packs/ · 行业包机制

每个行业包 = 一个 `packs/<行业>/` 子目录，至少包含：
- `RULES.md`：行业专属纪律（P2 级），覆盖默认包
- `config/*.json` 复写（来自默认 `config/`，按需调整）
  - `采集清单.json`
  - `标的池.json`
  - `口径字典.json`
  - `权威源映射.json`（覆盖默认字段映射）
  - `时点对齐.json`
  - `channels.json`（最后验证日期 + 降级链）

## 切换行业包

v0.1.0 行业包机制为声明式：每个行业包自带 `config/*.json` 与 `RULES.md`，调用方通过 `--pack <行业名>` 在 `manifest.json` 中标注本期所用的包；v0.2.0 将提供 `scripts/pack.py list / activate / wizard`。

```bash
# 跑本期月报时引用
python scripts/run_pipeline.py --old <old.docx> --ym 2026-08 --pack aerospace
```

## 已注册包

- `_default`：通用兜底（任何行业未指定时使用）

## 编写行业包的最小纪律

1. `RULES.md` 必须覆盖 6 条默认纪律（数据时点 / 来源时效 / 缺失处理 / 币种一致 / 跨期可比 / 结构型字段）
2. `config/*.json` 必须通过对应 `_schemas/*.schema.json` 校验（`adapt_json.py load_*` 会自动校验）
3. `标的池.json` 至少含 1 家公司（否则 `extract_numbers` 找无可对齐业务键）