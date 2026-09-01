# P0/P1/P2 纪律详解

> 来源：SKILL.md 主文件末尾的「关键纪律」段。本文件是其展开版。

## P0 阻断级（违反 = 返工 / 未交付）

| # | 纪律 | 实现位置 |
| --- | --- | --- |
| 1 | 禁止编造 | 拿不到 → `「本期无法获取 / —」` |
| 2 | 重新采集不沿用 | 时点型按月重采完整枚举 |
| 3 | 工具实测先于标 ✅ | `tool_inventory.py` 机检 |
| 4 | 来源逐条标注 | 溯源.jsonl 数值类带锚点 |
| 5 | 数值回读通过 | `audit/verify_value.py` |
| 6 | 名单/异常有交代 | `audit/reasonableness_check.py` |
| 7 | 盲审通过 | `templates/subagent_任务.md` 第六节 |
| 8 | 格式对齐 ≥95% | `audit/format_diff.py` |
| 9 | 空值必补 | `audit/diff_empty.py`（业务键对齐） |
| 10 | 口径漂移暂停 | `scripts/snapshot.py diff` ≥3 项触发 |
| 11 | 产出必达工作区 | `scripts/archive_to_workspace.py` |

## P1 警告级（须如实记录并可追溯，不阻断交付）

| # | 纪律 | 实现位置 |
| --- | --- | --- |
| 1 | 一次性确认：必填 ≤5 条 | `templates/确认清单.md` |
| 2 | 字段口径一致 | `config/口径字典.json` |
| 3 | 时点统一 | `config/时点对齐.json` |
| 4 | 财报期双轨 | 源文件标期 + 正文脚注 |
| 5 | 差距如实报告 | TOC F9 / 图表未更新等 |
| 6 | 通道降级可追溯 | `变更摘要.md` 第 4 节 |
| 7 | 每表对应章节+具体来源 | 源文件命名约定 |
| 8 | 归档完整 | runs/<run-id>/ 六件套 |

## P2 行业包级

见 `packs/<行业>/RULES.md`，**不**在主 SKILL.md 重述。

## 结构化 guard（v1 新增）

`scripts/pipeline_gate.py` 在 archive 之前自动检查 11 条 P0 中可自动验证的 6 条：
- P0-3 / P0-5 / P0-7 / P0-8 / P0-9 / P0-11

未通过 → exit 1，archive_to_workspace.py 必须等通过后再执行。