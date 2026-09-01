# 使用说明（USAGE）

> gfreport-renew-skill v0.2.0 · 行业月报端到端更新流水线
> 本文面向**使用者**（每月执行月报更新的人）。修改/扩展方法见 [docs/EXAMPLES.md](EXAMPLES.md)。

---

## 1. 三十秒理解

你给：上期月报 `.docx` + 目标月份。
它做：重采当月数据 → 按原格式改写 → 11 道自动质检 → 整套产出镜像到你的工作区。
铁律：**旧月报只是格式模具，一个旧数字都不沿用**；每个新数字都能回查到源文件。

```
python scripts/run_pipeline.py --old ./上月.docx --ym 2026-08 --ws "D:\工作区"
```

---

## 2. 安装

### 2.1 Python 依赖

```bash
pip install -r requirements.txt
```

| 依赖 | 用途 | 注意 |
| --- | --- | --- |
| python-docx | docx 读写 | |
| jsonschema | 配置强校验 | |
| requests | 通道体检 | |
| pandas / openpyxl | 数据表处理 | |
| **xlrd==1.2.0** | 上交所老式 .xls | **必须 1.2.0**，2.0+ 会报错（详见 Gotchas #10） |

### 2.2 安装到各工具（任选其一）

```bash
bash install.sh          # Linux/macOS
pwsh -File install.ps1   # Windows（Junction 方式，不复制文件）
```

安装器会把本 Skill 链接进 12 个 Tier-1 工具的原生路径 + `~/.agents/skills/` 通用兜底。

### 2.3 Claude Code marketplace 方式

先把本仓库上传 GitHub，然后在 Claude Code 中：

```
/plugin marketplace add <owner>/<repo>
```

### 2.4 验证安装

```bash
python scripts/run_pipeline.py --help          # 能打印参数即 OK
python evals/cases/make_fixtures.py            # 生成冒烟样本
python scripts/run_evals.py --rollout          # 回归测试全绿
```

---

## 3. 首次运行前检查单

- [ ] 上期月报 `.docx` 在手（只有 PDF？先跑 `python scripts/pdf_to_docx.py --pdf x.pdf --out x.docx`）
- [ ] 目标月份确定（`YYYY-MM`）
- [ ] `config/采集清单.json` 的 `截至日期` 已改为本期
- [ ] 行业包就绪：`--pack <行业>`（默认 `_default`；aerospace 已内置）
- [ ] 行业月度关键词表已更新：`packs/<行业>/config/新鲜度关键词.json`（新增当月条目）
- [ ] 工作区路径确定（`--ws`），或用 `--anchor` 指向旧月报所在目录反推

---

## 4. 每月例行 SOP

```bash
# ① 改配置（2 分钟）
#    config/采集清单.json → "截至日期": "2026-08-31"
#    packs/<行业>/config/新鲜度关键词.json → 新增 "2026-08": [...]

# ② 起跑（自动完成：数据流审计 → 通道体检 → 配置校验 → 采集计划 → 口径快照）
python scripts/run_pipeline.py --old ./7月.docx --ym 2026-08 --ws "D:\工作区" --pack aerospace

# ③ AI 执行两步（对话中完成）
#    Step 5  数据采集：按 download/采集计划.jsonl 调 MCP 工具，产出 sources/*.csv + 溯源.jsonl
#    Step 5.5 映射生成 + 保真改写：产出 output/新月报_2026-08.docx + output/变更摘要.md

# ④ 门禁复跑（自动完成 11 道门禁 + 盲审材料准备）
python scripts/run_pipeline.py --old ./7月.docx --ym 2026-08 --ws "D:\工作区" --resume

# ⑤ AI 盲审（Step 8）：独立子 Agent 只看产出挑错；不过 → 修正后重跑 ④

# ⑥ 收工：全部硬门禁 ✅ 后自动镜像到工作区（P0-11，不镜像 = 未交付）
```

**内容重建模式**（当月表格结构大改是预期时）：

```bash
python scripts/run_pipeline.py --old ./7月.docx --ym 2026-08 --ws "D:\工作区" \
    --soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff
```

降级门禁失败记 ⚠️ 转盲审，不阻断交付，但**绝不静默放行**。

---

## 5. 产出物解读

```
<工作区>/<产品>_产出/
├── 新月报_2026-08.docx    ← 最终交付（格式与上期一致）
├── 变更摘要.md            ← 本期改了什么、异常波动、新增/移除标的（环比必读）
├── SUMMARY.md             ← 全部门禁状态单页汇总
├── 输入/                  ← 上期月报存档
├── 源文件/                ← 9 张 source_*.csv + 溯源.jsonl + 通道实测.jsonl
│     溯源.jsonl：每个数字的"户口本"——cell / value / source_file / url / 交叉验证
└── 门禁报告/              ← 11 份门禁报告（01-11）+ 通道健康度
```

**审阅顺序建议**：SUMMARY（门禁是否全绿）→ 变更摘要（本期差异）→ 门禁报告/08（数值回读明细）→ 抽 3 个数字按溯源回查 → 打开 docx 目视图表。

---

## 6. 11 道门禁速查

| # | 名称 | 一句话 | 失败先看 |
| --- | --- | --- | --- |
| 01 | 数字提取 | 旧报数字登记造册 | 从不阻断 |
| 02 | 配置校验 | 配置表 schema + 通道名合法 | 采集清单里的通道名拼写 |
| 03 | 空值 diff | 上期有值本期不能空 | 变更摘要是否点名了移除 |
| 04 | 一致性 | 合计=分项和 | 表格合计行公式 |
| 05 | 交叉一致性 | 正文断言 vs 表格行数/分组求和/加总式 | 05 报告的 ❌/⚠️ 清单 |
| 06 | 合理性 | 环比±50%、增删标的要有交代 | 变更摘要.md |
| 07 | 格式对比 | 相似度≥95% + 结构差清单（表数/图片数） | 是否该用 --soft-gates |
| 08 | 数值回读 | 溯源值=CSV 值 **且真的写在 docx 里** | "幽灵条目"= docx 里没有 |
| 09 | 溯源反查 | 覆盖率≥90% + 交叉验证 | 缺 source_file/url 的条目 |
| 10 | 内容新鲜度 | 当月关键词命中≥50% | 行业词表是否更新 |
| 11 | 跨月去重 | 上期事件不重复报、无名主体拦截 | 11 报告的同指纹清单 |

软硬口径：默认全硬；`--soft-gates 03_diff_empty,06_reasonableness_check,07_format_diff` 可显式降级（记录 ⚠️ 转盲审）。
**哈希绑定**：每道门禁记录所验 docx 的 SHA-256；与交付物指纹不一致 = 硬失败，`--resume` 时指纹变了会强制重验。

---

## 7. 常见故障排查

| 症状 | 原因 | 处置 |
| --- | --- | --- |
| `❌ 无法确定工作区` | 未传 --ws 且探测全部失效 | 显式传 `--ws` 或 `--anchor <旧月报路径>` |
| `❌ 工作区与 skill 基目录冲突` | --ws 误指到 skill 安装目录 | 换成真实工作目录（守卫防止产物写回包内） |
| 05 报 `SKIPPED（claim=0）` | 正文无任何汇总断言 | 门禁未生效 ≠ 通过；人工复核叙述层 |
| 08 大量"幽灵条目" | 溯源写了 docx 里没有的数 | 逐条修正溯源.jsonl 或补写正文 |
| 07 报"自比检测" | old 与 new 是同一文件 | 检查 --old/--new 是否传错 |
| 11 报"未定位到投融资表" | 表头不符合启发式 | 盲审人工核对，或调整表头关键词 |
| 通道大面积 ❌ | 网络/官网 WAF | 看 通道健康度报告 的降级链提示 |
| `xlrd` 报错 | 装了 2.0+ | `pip install xlrd==1.2.0` |
| 门禁报告显示 PASS 但 SUMMARY 缺门禁 | 旧版行为（v0.1.0 bug） | 已修复；升级到 v0.2.0 |
| `--resume` 全部强制重跑 | 新月报被重新生成（指纹变了） | 符合预期：指纹变了必须重验 |

---

## 8. 命令参考（run_pipeline.py）

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--old` | ✅ | 上期月报 docx 路径 |
| `--ym` | ✅ | 目标月份 YYYY-MM |
| `--ws` | — | 工作区路径（与 --anchor 二选一） |
| `--anchor` | — | 旧月报路径（反推工作区） |
| `--pack` | — | 行业包名，默认 `_default` |
| `--product` | — | 产出目录前缀，默认 `行业月报` |
| `--key-col-name` | — | diff_empty/去重业务键列名，默认 `公司简称` |
| `--format-threshold` | — | 格式相似度阈值，默认 0.95 |
| `--format-struct-strict` | — | 结构差（表数/图片数）非零即失败 |
| `--freshness-threshold` | — | 新鲜度命中率阈值，默认 0.5 |
| `--soft-gates` | — | 逗号分隔的硬门禁降级清单 |
| `--jsonl` | — | 溯源.jsonl 路径（默认 runs/<run-id>/sources/） |
| `--roster-note` | — | 变更摘要路径（默认 runs/<run-id>/output/） |
| `--resume` | — | 断点续跑（跳过已过且指纹未变的门禁） |
| `--run-id` | — | 指定 run-id 续跑 |

退出码：`0` 全部通过 / `1` 任一硬门禁失败 / `2` 前置条件失败。

---

## 9. 维护清单

**每月**：改 `采集清单.json` 截至日期 → 更新行业包月度关键词 → 跑 SOP → 检查通道健康度趋势。
**每季**：核对 `endpoints.json` 官网接口是否改版；`口径快照/` diff 漂移是否 ≥3 项；`xlrd` 等依赖 pin 是否仍必要。
**升级**：读 `CHANGELOG.md`；`runs/`、`state/` 永远不入库（.gitignore 已排除）；发布前跑 `python scripts/run_evals.py --rollout` + validate + security_scan 三门禁。
