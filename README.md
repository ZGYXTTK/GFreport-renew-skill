# GFreport-renew-skill

> **广发证券行业月报端到端更新流水线** · Agent Skill（[Agent Skills Open Standard](https://agentskills.io) 兼容）
> 以上期月报 docx 为模具：按月重采数据 → 保留格式改写 → **11 道门禁质检（哈希绑定交付物指纹）** → 整套产出镜像到工作区。

![license](https://img.shields.io/badge/license-Apache--2.0-green)
![version](https://img.shields.io/badge/version-0.2.0-blue)
![python](https://img.shields.io/badge/python-3.10%2B-informational)
![gates](https://img.shields.io/badge/gates-11%20%28hard%20default%29-orange)

---

## 它解决什么问题

| 月报更新的痛点 | 本 Skill 的对策 |
| --- | --- |
| 手工抄数易错易漏 | 每个数字强制溯源到源 CSV，脚本逐个回读核对（含币种/单位折算） |
| 汇总数字与表格对不上 | 交叉一致性门禁：正文断言 vs 表格行数 / 分组求和 / 加总等式 |
| 上期事件本月重复报 | 跨月去重门禁：「主体+轮次」指纹跨期比对 + 无名主体拦截 |
| 格式改坏（丢图表/丢列/字体错乱） | 就地改写（复制底稿逐 run 克隆格式），禁止从零重建 |
| 质检对象 ≠ 交付对象 | 全门禁 SHA-256 哈希绑定：验过的文档必须就是交付的文档 |
| 拿不到数据就编 | 铁律：标「本期无法获取 / —」，禁止编造与模糊占位 |

一句话：**旧月报只是格式模具，一个旧数字都不沿用**。

## 5 分钟上手

```bash
# 1. 依赖（注意 xlrd 必须 1.2.0，读上交所老式 .xls）
pip install -r requirements.txt

# 2. 安装到本机工具（12 个 Tier-1 工具 + ~/.agents/skills 通用兜底）
pwsh -File install.ps1      # Windows
bash install.sh             # Linux/macOS

# 3. 冒烟验证（fixtures 正负双向）
python evals/cases/make_fixtures.py && python scripts/run_evals.py --rollout

# 4. 首跑
python scripts/run_pipeline.py --old ./上月.docx --ym 2026-08 --ws "D:\工作区" --pack aerospace
```

采集与盲审两步由 AI 在对话中完成，其余全自动。完整 SOP 见 [docs/USAGE.md](docs/USAGE.md)。

## 安装

### 方式 1 · Claude Code marketplace

```
/plugin marketplace add ZGYXTTK/GFreport-renew-skill
```

### 方式 2 · 安装器（推荐）

```bash
bash install.sh          # Linux/macOS（symlink）
pwsh -File install.ps1   # Windows（Junction，非管理员可用）
```

### 方式 3 · git clone 到工具原生路径

```bash
git clone https://github.com/ZGYXTTK/GFreport-renew-skill.git <目标路径>/gfreport-renew-skill
```

| 工具 | 原生路径 |
| --- | --- |
| Claude Code | `~/.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Cursor | `%APPDATA%\Cursor\User\skills\`（Win）/ `~/.config/Cursor/User/skills/` |
| Codex CLI | `~/.config/Codex/skills/` |
| Goose | `~/.config/goose/skills/` |
| Roo Code / Cline / Kilo / Kiro / Factory / Antigravity | `~/.config/<工具>/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| 通用兜底（任何读取 AGENTS.md 的工具） | `~/.agents/skills/` |

> Tier 2/3（Windsurf / Trae / Junie / Zed / Augment / Aider / Continue.dev）：v0.2.0 未声明兼容，安装路径与转写规则按 roadmap 补充。

## 目录

```
GFreport-renew-skill/
├── SKILL.md               # 主入口（触发词 + 铁律 + 流程 + Gotchas）
├── AGENTS.md              # Codex CLI 等优先读取的精简入口
├── README.md              # 本文件
├── docs/
│   ├── USAGE.md           # 使用说明：每月 SOP / 门禁速查 / 故障排查 / 命令参考
│   └── EXAMPLES.md        # 修改示例：新增行业包 / 采集项 / 门禁 / 端点（8 例）
├── discovery.json         # 决策契约（何时触发/拒绝、权限边界、语义契约）
├── config/                # 跨月复用配置（endpoints / 采集清单 / 口径 / 标的池 + schema）
├── packs/                 # 行业包（_default 兜底 + aerospace；换行业只换包）
├── scripts/
│   ├── run_pipeline.py    # 单一编排入口（哈希绑定 + --soft-gates + --resume）
│   ├── build_report_v2.py # 保真改写器（docx_utils：超链接/多run/合并单元格）
│   ├── collect.py         # 采集计划（MCP 只能由宿主 Agent 调用）
│   ├── channel_health.py  # 通道体检（10 官网直探 + MCP 实测回写校验）
│   └── audit/             # 11 道门禁（01-11）
├── evals/                 # 回归测试（fixtures 正负双向冒烟）
├── references/            # 深度文档（10 步详解 / P0-P2 纪律 / 12 条避坑）
└── templates/             # 确认清单 / 子agent任务书 / 溯源 schema
```

## 11 道门禁一览

| # | 门禁 | 一句话 |
| --- | --- | --- |
| 01 | 数字提取 | 旧报数字登记造册 |
| 02 | 配置校验 | 配置 schema 强校验 + 通道名合法性 |
| 03 | 空值 diff | 上期有值本期不能空（可降软） |
| 04 | 一致性 | 合计 = 分项和 |
| 05 | 交叉一致性 | 正文断言 vs 表格行数 / 分组求和 / 加总等式（自动排除 Y16 型号） |
| 06 | 合理性 | 环比 ±50%、增删标的必须有交代（可降软） |
| 07 | 格式对比 | 相似度 ≥95% + 结构差清单（表数/图片数）+ 自比检测（可降软） |
| 08 | 数值回读 | 溯源值 = 源 CSV **且真的写在交付 docx 里**（真·docx 回读） |
| 09 | 溯源反查 | 覆盖率 ≥90% + 逐条交叉验证 |
| 10 | 内容新鲜度 | 行业月度关键词命中 ≥50%，防"新瓶装旧酒"（词表按 pack 配置） |
| 11 | 跨月去重 | 「主体+轮次」指纹跨期比对；金额矛盾/无名主体 = 硬伤 |

全门禁默认硬失败阻断；内容重建模式用 `--soft-gates` 显式降级（记 ⚠️ 转盲审，绝不静默放行）。
每道门禁执行时记录所验 docx 的 SHA-256——与交付物指纹不一致 = 硬失败。

## 与原 industry-report-update v2.1 的差异

| 维度 | 原 v2.1 | 本 v0.2.0 |
| --- | --- | --- |
| 前置元数据 | 缺 discovery/AGENTS/license | 全齐 + docs/ 双手册 |
| 配置 | 7 个 YAML 弱校验 | 8 组 JSON + jsonschema 强校验 |
| 编排 | 9 门禁 + Agent 口头调度 | run_pipeline 单入口，11 门禁 + 哈希绑定 + --soft-gates/--resume |
| 数值回读 | 溯源自证 | **真·docx 回读**（metric 关键词定位 docx 行 + CSV 双侧） |
| 跨月安全 | 无 | 去重指纹门禁 + 口径快照 diff + 哈希绑定 |
| 评估 | 手工 | fixtures 正负双向冒烟 + run_evals 一键 |
| 开源合规 | 无 | LICENSE + .gitignore（runs/state 不入库）+ CHANGELOG |

## 触发词

`行业月报更新` / `月报更新` / `生成最新月报` / `更新月报` / `广发月报` / `重新生成月报` / `generate monthly report`

不适用（discovery.json 声明拒绝）：周报/季报/年报、双公司专题对比（走姊妹 Skill）、无上期模板从零写、只给主题不给旧报路径。

## 兼容性（v0.2.0 实际声明）

- **Tier 1（原生 SKILL.md，12 工具）**：Claude Code / Cursor / Gemini / Kiro / Goose / OpenCode / Cline / Roo / Kilo / Factory / Antigravity / Codex CLI
- **Tier 2/3**：未声明兼容（v0.2.1+ 补充）
- 运行环境：Python 3.10+；MCP 数据通道（iFinD / Wind / 企查查 / IT桔子 / Tavily 等）需宿主环境配置，缺失时按降级链降级并如实标注

## 质量与验证状态（v0.2.0 发布基线）

| 门禁 | 结果 |
| --- | --- |
| agent-skill-creator `validate.py` | **VALID**（0 WARN） |
| agent-skill-creator `security_scan.py` | **CLEAN**（0 HIGH/MED/LOW） |
| evals 冒烟 | 正向 5✅ 不误杀 / 负向幽灵+错值 2/2 拦截 / 门禁结构 11 硬门禁 ✓ |
| 真实期回归（2026-08 期） | 此前漏掉的每类事故（幽灵条目 / 金额矛盾 / 无名主体 / 结构退化）均被新门禁拦截 |

详细证据与变更记录见 [CHANGELOG.md](CHANGELOG.md)；隐私边界（`runs/`、`state/` 为运行痕迹，已 .gitignore）见仓库根 `.gitignore`。
