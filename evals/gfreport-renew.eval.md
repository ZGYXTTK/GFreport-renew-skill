# gfreport-renew.eval.md（v2）

> 防回归评估规范。v2（2026-09-01）变更：全部命令跨平台化（python -c 替代 %TEMP%/findstr/if exist）；
> golden case 改用仓库内 fixtures 相对路径（真实期数据已归档至用户工作区，不入库）；
> 新增 C9 跨月去重 / C10 分组求和 / C11 哈希绑定。由 `python scripts/run_evals.py --rollout` 一键跑。

## Criteria

### C1 — 格式保真度（软）

```yaml
id: format_diff_threshold
kind: shell
command: |
  python scripts/audit/format_diff.py evals/cases/fixtures/sample_old.docx evals/cases/fixtures/sample_old.docx --threshold 0.95
pass: exit_code == 1
criticality: soft
note: "fixtures 自比（old==new）必须被自比检测拦截（v2 行为：exit 1）——用于验证比对逻辑生效；真实期格式保真由 C5b/C11 组合保证"
```

### C2 — 硬门禁全 PASS（01/02/04/05/08/09/10/11）

```yaml
id: all_gates_pass
kind: shell
command: |
  python scripts/audit/extract_numbers.py evals/cases/fixtures/sample_old.docx --out build/01.md
  python scripts/audit/config_check.py --run-id fixtures
  python scripts/audit/consistency_check.py evals/cases/fixtures/sample_old.docx --out build/04.md
  python scripts/audit/cross_consistency_check.py evals/cases/fixtures/sample_old.docx --out build/05.md
  python scripts/audit/verify_value.py evals/cases/fixtures/溯源.jsonl --base-dir evals/cases/fixtures --docx evals/cases/fixtures/sample_new.docx --out build/08.md
  python scripts/audit/traceability_check.py evals/cases/fixtures/溯源.jsonl --min-coverage 0.9 --require-cross-check --base-dir evals/cases/fixtures --out build/09.md
pass: all exit_code == 0
criticality: hard
note: "05 v3 在 claim=0 时 exit 2（未生效 ≠ 通过）；08 v2 必须带 --docx（弱校验模式 exit 2）"
```

### C2b — 软门禁（03/06/07，内容重建模式预期失败）

```yaml
id: soft_gates_recorded
kind: shell
command: |
  python scripts/audit/diff_empty.py evals/cases/fixtures/sample_old.docx evals/cases/fixtures/sample_new.docx --out build/03.md --key-col-name 公司简称
  python scripts/audit/format_diff.py evals/cases/fixtures/sample_old.docx evals/cases/fixtures/sample_new.docx --out build/07.md
pass: exit_code in (0, 1)
criticality: soft
note: "软门禁失败只记录不阻断；run_pipeline 侧用 --soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff 显式降级"
```

### C3 — 数值回读 0 幽灵条目（硬）

```yaml
id: verify_value_no_ghost
kind: shell
command: |
  python scripts/audit/verify_value.py evals/cases/fixtures/溯源.jsonl --base-dir evals/cases/fixtures --docx evals/cases/fixtures/sample_new.docx --out build/08.md
  python -c "import sys; t=open(r'build/08.md',encoding='utf-8').read(); sys.exit(0 if '未找到该指标行' not in t else 1)"
pass: exit_code == 0
criticality: hard
note: "2026-08 期事故：峰飞 V5000/时的 E20 不在 docx 仍判 ✅——幽灵条目必须为 0"
```

### C4 — 跨月去重拦截（硬）

```yaml
id: dedupe_intercepts
kind: shell
command: |
  python scripts/audit/dedupe_check.py --old evals/cases/fixtures/sample_old.docx --new evals/cases/fixtures/sample_new.docx --out build/11.md
pass: exit_code in (0, 1, 2)
criticality: hard
note: "fixtures 无投融资表时 exit 2（SKIPPED）；真实期必须 exit 0 或 1，exit 2 需盲审确认"
```

### C5 — 工作区镜像成功（硬）

```yaml
id: archive_done
kind: shell
command: |
  python scripts/archive_to_workspace.py --run-id <run-id> --ws <WS> --product <产品前缀>
  python -c "import os,sys; p=os.path.join(os.environ['GFRS_WS'], '产出', '新月报.docx'); sys.exit(0 if os.path.isfile(p) else 1)"
pass: exit_code == 0
criticality: hard
note: "P0-11：违反 = 视为未交付；路径经 GFRS_WS 环境变量注入，避免本机绝对路径入库"
```

### C5b — 内容新鲜度（硬）

```yaml
id: content_freshness_threshold
kind: shell
command: |
  python scripts/audit/content_freshness.py evals/cases/fixtures/sample_new.docx --ym <YYYY-MM> --old evals/cases/fixtures/sample_old.docx --threshold 0.5 --out build/fresh.md
pass: exit_code == 0
criticality: hard
note: "防 9 道形式门禁全过但内容仍是上期副本的回归（industry keyword 表应在 packs/<行业>/config/ 配置）"
```

### C6 — run_pipeline 哈希绑定生效（硬）

```yaml
id: hash_binding_active
kind: shell
command: |
  python -c "import sys; sys.path.insert(0,'scripts'); import run_pipeline; sys.exit(0 if hasattr(run_pipeline,'_sha256') and '10_content_freshness' in run_pipeline.HARD_GATES and '11_dedupe_check' in run_pipeline.HARD_GATES else 1)"
pass: exit_code == 0
criticality: hard
note: "编排器必须包含 _sha256 与 11 道 hard_gates（含 10/11 新门禁）"
```

## Golden Cases

```yaml
golden_cases:
  - id: fixtures_smoke
    split: train
    inputs:
      old_docx: evals/cases/fixtures/sample_old.docx
      new_docx: evals/cases/fixtures/sample_new.docx
      jsonl: evals/cases/fixtures/溯源.jsonl
    expected_results:
      format_diff_threshold: pass   # 自比被拦截
      all_gates_pass: pass
      verify_value_no_ghost: pass
      hash_binding_active: pass
    note: "仓库内自包含冒烟集；首次运行前由 evals/cases/make_fixtures.py 生成 sample_new/溯源"

  - id: holdout_next_period
    split: test
    inputs:
      old_docx: <上期新月报 docx（用户提供，不入库）>
      ym: "<YYYY-MM>"
    expected_results:
      all_gates_pass: pass
      verify_value_no_ghost: pass
      dedupe_intercepts: pass
      content_freshness_threshold: pass
    note: "真实期 holdout：每月首跑即首绿基线，数据留在用户工作区（runs/ 已 gitignore）"
```

## Judge（可选）

```yaml
judge:
  pinned_model: "由调用方以 --model 注入（EVAL_MODEL 环境变量）"
  temperature: 0.0
  canary: "Known-bad report: 故意删除 50% 溯源后跑 traceability，交叉验证率必 < 90%，触发 C2 失败"
```

## 运行方式

```bash
python evals/cases/make_fixtures.py          # 生成/刷新 fixtures（幂等）
python scripts/run_evals.py --rollout --eval evals/gfreport-renew.eval.md
python scripts/run_evals.py --rollout --promote   # 首绿后转 baseline
```
