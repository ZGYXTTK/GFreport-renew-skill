# 回归评估（evals）说明

> `evals/gfreport-renew.eval.md` 是 `autoresearch-universal` 可消费的规格文件。
> `scripts/run_evals.py --rollout` 执行 binary checks。
> 详见 SKILL.md "评估 / 修订记录"段。

## 5 道 binary check

1. **python-docx installed** — 必备依赖
2. **jsonschema installed** — config schema 校验依赖（无则 WARN）
3. **all 7 JSON configs pass schema** — `scripts/adapt_json.py` 一键诊断
4. **all 9 audit scripts compile** — 防止语法错
5. **run_pipeline.py --help shows --old flag** — 防止 CLI 退化

## golden case

`evals/cases/fixtures/sample_old.docx`：1 标题 + 1 段落（含"共 16 家在审 / 1.2 亿元") + 1 张 4 列 5 行表。用 `python evals/cases/make_fixtures.py` 生成。

## holdout case

`split: "test"`，仅在 release 时跑，不进入优化循环。

## known-bad canary

故意篡改 `config/endpoints.json` 的 `name`，跑 eval expect exit 1。
用于校准 `llm-judge`：确保 judge 看到 canary 时确实判 fail。

## 添加新 case

1. `evals/cases/<name>/input.yaml` — 输入描述
2. `evals/cases/<name>/expected.md` — 期望输出清单
3. `evals/cases/<name>/fixtures/` — 必要 fixture
4. 在 `evals/gfreport-renew.eval.md` 的 `## Cases` 段加 case 块

## promote baseline

```bash
# 第一次跑通后，固化 baseline
python scripts/run_evals.py --rollout > evals/baseline.txt

# 后续回归对比
python scripts/run_evals.py --rollout > evals/current.txt
diff evals/baseline.txt evals/current.txt
```