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
5. 用同一次 `run_id` 调用 `get_stock_research_data`。不要传 `symbols`，让工具展开已保存的前 5 名。不要研究候选以外的代码。
6. 如果这一步失败，停止。`valuation`、`news`、`fund_flow` 为空是因为没有接入，不能写成“暂无利空”，也不能补财务或新闻。
7. 用同一次 `run_id` 调用 `check_stock_risk`。不要传代码或文件路径。`block` 表示移出重点研究。`warn` 不是卖出建议。
8. 用同一次 `run_id` 调用 `generate_daily_report`。只引用这一步 JSON 和报告文件里的数字。不要改写表格。行业一节是候选行业分布，不是全市场板块排名。
9. 向用户摘要 `data_date`、市场环境、候选、重点研究和风险命中。观察条件只复述规则失效，不写成委托。
10. 不要调用下单、转账或登录券商的工具。`run_daily_research` 不是会话工具；只有人在终端执行 CLI 时才作为备用。
