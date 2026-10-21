# A 股盘后研究工作流

这份文件给人读，DSH 不会因为目录里有它就自动执行。可加载的步骤说明在 `.dsh/skills/daily-stock-research/SKILL.md`。Day 1 的 Skill 对模型关闭，避免健康检查被半成品流程带走。

## 目标

分析市场环境，按确定性规则筛选候选股票，做风险检查，并生成可追溯的研究报告。

## 步骤

1. 调用 `get_market_snapshot`。失败则停止，不编造行情。
2. 用同一次 `run_id` 调用 `screen_stocks`。
3. 对少量候选调用 `get_stock_research_data` 和 `check_stock_risk`。
4. 调用 `generate_daily_report`。

Day 1 只注册了 `ping_research`，用来确认插件能被 Agent 调用。
