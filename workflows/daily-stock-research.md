# A 股盘后研究工作流

这份文件给人读，DSH 不会因为目录里有它就自动执行。可加载的步骤说明在 `.dsh/skills/daily-stock-research/SKILL.md`。

## 目标

用 fixture 样本分析已经冻结的交易日，按确定性规则筛选候选股票。不接入实盘下单。

## 步骤

1. 调用 `get_market_snapshot`。失败则停止，不编造行情。
2. 用同一次 `run_id` 调用 `screen_stocks`。不要另传日期。
3. 用同一个 `run_id` 调用 `get_stock_research_data`，展开前 5 名。不补充财务、新闻或资金流。
4. 调用 `check_stock_risk`。警告只进入风险段，不改写成交易指令。
5. 调用 `generate_daily_report`。报告写到 `reports/<data_date>/<run_id>.md` 和同名 JSON。行业标题用“候选行业分布”。

`ping_research` 仍是健康检查，不读取行情。
