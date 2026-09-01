# Gotchas（避坑手册）

> SKILL.md 中 `## Gotchas` 段落的详细展开。
> 每条对应"模型不会自动发现、但跳过会出大事"的环境事实。

## 1. docx 超链接 run 改写

`cell.text = value` 会**留下旧文字**。原因：`docx` 把超链接存为 `<w:hyperlink>` 包 `<w:r>`，迭代 cell.paragraphs[0].runs 不会进到 hyperlink 内的 run。

✅ 改用 `scripts/docx_utils.py`：
- `set_cell_text_keep_fmt(cell, value)`：clone 首 run 的 rPr + 清空 hyperlink 内 run 的旧 text
- `set_para_text_keep_fmt(p, new_text)`：段落级
- `set_para_segments_keep_fmt(p, [("标题", {"b":True}), ("正文", None)])`：多段混合格式

## 2. 数字 + 单位字符串"1亿元"≠"1万元"

`verify_value.py` 的 `_UNITS` 表必须**先列复合单位**（`万亿美元`/`万亿元`/`亿美元`/`亿元`/`万美元`/`万元`/`美元`/`元`），单纯单位排在后面（最长匹配优先）。否则"1亿"先命中"亿"而非"万亿美元"。

## 3. 港股 IPO 6 个月未聆讯 = 失效条目

> 来自原 industry-report-update/packs/robotics/RULES.md 规则 1 的事实。

任何"基线-变化"高估都会把失效条目算入"在审"。需要：
- 在 `packs/<行业>/RULES.md` 显式说明
- `audit/diff_empty.py` 业务键比对能间接暴露：旧有港股条目消失但无变更摘要点名 → 触发 P0-6 硬伤

## 4. 招股书 PDF 不可获取

专题研究走 `专题研究.skill/`，不可获取时填 `「未取得招股书」`，禁止 "以招股书为准" 占位。

## 5. 原生 OOXML 图表门禁无法重算

格式对比只看 XML 签名，不渲染视觉。处理方式：
- 保留原图
- 图下加脚注：「本图数据截至旧期 YYYY-MM，最新数据见表 X」
- 把对应数据表列为必更新项

## 6. 上交所/深交所/北交所/证监会 WAF / SSL

| 站 | 已知问题 | 降级 |
| --- | --- | --- |
| 上交所 | 老式 .xls（OLE2），需 xlrd 解析 | mx-ds-mcp / iFinD |
| 深交所 | `projectrends` 分页失效（`page/start/count` 无效，仅 `pageSize` 上限 ~100） | iFinD |
| 证监会 | 必须 http 非 https（SSL 握手失败）；翻页 `csrcfd/index_N.html` | iFinD 辅导备案 |
| 北交所 | `bse.cn` WAF 重置（`ConnectionResetError 10054`） | 媒体降级 |
| hkexnews | 检索页 HTML | mx_hk_finance_data / iFinD |
| cninfo | 首页 HTML | qcc-document parse_document |

## 7. 子公司 vs 集团合并口径

`config/口径字典.json` 的 `法人统一工商名` 字段要求"全表统一"，但同一集团下可能有"母公司"和"上市子公司"两个独立工商主体。处理：
- `标的池.json` 按工商主体登记，不按"集团"
- `verify_value.py` 锚点匹配按工商名（含子集团后缀差异）
- `diff_empty.py` 键归一化会去掉 "股份有限公司 / 有限公司 / 控股集团 / 集团" 后缀，再做匹配

## 8. subagent 通道连续失败 ≥3 次

强制暂停。`scripts/channel_health.py` 的 subagent 状态在 `state/渠道历史.jsonl` 跨月累加，连续 3 期 ❌ → 提示人工检查模型路由。**不允许**主 Agent 静默接管后无标注。

## 9. 工作区探测退化为 cwd

`scripts/workspace.py` 优先级：--ws > --anchor > DSH_WORKSPACE > DSH_SESSION_JSONL > cwd。
若所有信号都失效或 cwd = skill 基目录，`archive_to_workspace.py` 触发 `_inside_base` 守卫 → SystemExit("请显式传 --ws 或 --anchor")。**不**静默写入。

## 10. .xls 老格式（xlrd 2.0+ 已不支持 .xlsx）

上交所 `query.sse.com.cn/commonExcelKcb.do` 返回 OLE2 .xls，**必须** `engine='xlrd'`，且 xlrd < 2.0 或安装 `xlrd==1.2.0`。xlrd 2.0+ 抛 `XLRDError: Excel xlsx file; not supported`。

## 11. docx 单元格里 `合计`/`总计` 的合计数在哪一列

`audit/consistency_check.py` 默认假设**最后一列是合计**，分项在前几列。如遇"合计在中间列"，需要手动调整脚本或拆分表。

## 12. 跨月 rebase 时不要直接覆盖 `config/*.json`

每月初新建 `config/口径快照/<YYYY-MM>.json` 落盘快照 → `snapshot.py diff --prev-ym <上月>` → 差异 ≥3 项必须暂停并请求用户确认 → 用户确认后**手动**改 `config/*.json` 并标注 version 号 + 备份旧版。**禁止**自动覆盖。