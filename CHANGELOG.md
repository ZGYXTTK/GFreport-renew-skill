# Changelog

遵循 Keep a Changelog 约定；版本号遵循 SemVer。

## [0.2.0] - 2026-09-01

> 本版由 2026-09-01 双线审计驱动：Skill 结构审计（agent-skill-creator `--audit` 流程）
> + 2026-08 期产出月报的投资研究员评审（47/100，10/18 抽样一致率）。

### Added
- `LICENSE`（Apache-2.0 全文）——开源发布前提件。
- `.gitignore`：`runs/`、`state/`、`__pycache__`、`*.pyc`、`*.log` 等运行痕迹不入库。
- `CHANGELOG.md`。
- `scripts/audit/dedupe_check.py`（门禁 11）：跨月投融资事件去重——按「主体+轮次」指纹
  比对上期/本期表格，同指纹重复或金额矛盾即拦截；无名主体（如「北方某产业机构」）判硬伤。
- `scripts/audit/verify_value.py --docx`：**真·docx 回读**——按溯源 metric 关键词定位
  新月报表格行，校验 docx 中实际存在的值与源 CSV 一致；不再「溯源值 vs 源文件」自证清白
  （修复 2026-08 期「峰飞 V5000/时的 E20 不在 docx 仍判 ✅」事故）。
- `run_pipeline.py` 哈希绑定：gate_state 记录每道门禁执行时的 old/new docx SHA-256；
  汇总时任何门禁的文档指纹与本次交付指纹不一致 → 判失败（修复「04/06 跑在旧 run 中间稿」事故）。

### Changed
- `scripts/audit/content_freshness.py` v2：行业关键词表从引擎硬编码（DEFAULT_KEYWORDS_BY_YM）
  迁出至 `packs/<pack>/config/新鲜度关键词.json`（结构 `{"<YYYY-MM>": [...], "default": [...]}`）；
  未配置时退化为 ym 泛化 2 条并标注「泛化模式」。修复「换行业/换月词表失效」缺陷。
- `evals/gfreport-renew.eval.md` v2：全部命令跨平台化（python -c 替代 %TEMP%/findstr/if exist）；
  golden case 改用仓库内 fixtures 相对路径；新增正负双向冒烟（正向 5 条不误杀、
  负向幽灵/错值必拦截）；`evals/cases/make_fixtures.py` 升级为自举冒烟集生成器。
- `scripts/audit/cross_consistency_check.py` v3：汇总断言提取由 4 种模式扩为全量纲
  （颗/笔/次/单/条/项/起/架/型/款/轮）+ 「N+M+K=L」加总等式校验 + 分组求和 vs 表行数校验 +
  型号数字（Y16）排除 + 弱断言/分组叙述降级为警告；claim=0 判
  SKIPPED（⚠️ 门禁未生效）而非 ✅（修复 2026-08 期「载荷 31 颗 vs 表内 30 颗」「17 笔 vs 15 行」漏网）。
- `scripts/audit/format_diff.py` v2：输出结构差清单（表格数差、逐表行列差、内嵌图片数差）；
  图片 10→0、表 19→13 这类结构退化不再以「相似度 100%」蒙混；新增自比检测
  （old/new 哈希相同即报错）与 `--struct-strict` 开关。
- SKILL.md：修复步骤 6 断链（`scripts/run.py` 不存在 → `run_pipeline.py --resume`）。
- README：纠正「10 步全部 Python 化」失实表述（Step 4 确认 / 5 采集 / 5.5 映射 / 8 盲审由 Agent 执行）。
- frontmatter `python_packages` 与 `requirements.txt` 对齐（补 pandas / xlrd / openpyxl）。

### Removed
- `runs/`（10 个运行目录，含内部研报 docx ×8）、`state/渠道历史.jsonl`——已归档至
  `skills/_archive/gfreport-renew-skill-runs-state-20260901.zip`（5.87 MB）后删除；
  用户工作区 `*_产出/` 镜像不受影响。
- 包根目录 3 个误提交的门禁产物：`02_config_check.md`、`07_format_diff.md`、`content_freshness.md`。
- `scripts/**/__pycache__`（4 个 .pyc）。

### Security
- security_scan 36 HIGH（`runs/**/*.csv` 的 UTF-8 BOM 误报源）随 runs/ 清理归零。

## [0.1.0] - 2026-08-31

- 初版：10 步闭环编排（run_pipeline.py）、9 道门禁（audit/*.py）、行业包（packs/）机制、
  JSON schema 强校验配置、evals 回归、双安装器、discovery.json 决策契约。
