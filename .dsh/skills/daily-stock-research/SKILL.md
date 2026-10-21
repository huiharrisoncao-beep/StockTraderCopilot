---
name: daily-stock-research
description: Run the fixture-backed A-share after-close research flow. Use when the user asks for 盘后研究, 每日研究, 选股报告, or asks to load daily-stock-research.
---

# A 股盘后研究

只使用已注册工具。数字只引用工具 JSON。不给出买卖指令。

1. 调用 `get_market_snapshot`，`universe` 为 `demo`。除非用户明确给出日期，否则不要传 `as_of`。
2. 如果这一步 `ok` 不是 `true`，停止。说明 `error.code`，不要进入选股，也不要用记忆补行情。
3. 用同一次返回的 `run_id` 调用 `screen_stocks`。可以传 `rule_set=trend_volume_v1`。不要另传 `data_date`，不要改日期重跑。
4. 向用户展示 `data_date`、指数、涨跌家数范围、候选表和警告。空候选是合法结果。
5. `get_stock_research_data`、`check_stock_risk` 和 `generate_daily_report` 尚未接入。不要调用不存在的工具。说明个股研究未展开，并保留筛选 JSON 里的命中字段。
