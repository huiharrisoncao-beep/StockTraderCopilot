# A 股盘后研究工作流

这份文件给人读，DSH 不会因为目录里有它就自动执行。可加载的步骤说明在 `.dsh/skills/daily-stock-research/SKILL.md`。

## 目标

用 fixture 样本分析已经冻结的交易日，按确定性规则筛选候选股票。不接入实盘下单。

## 步骤

1. 调用 `get_market_snapshot`。失败则停止，不编造行情。
2. 用同一次 `run_id` 调用 `screen_stocks`。不要另传日期。
3. 个股研究、风险检查和报告工具留到 Day 4。Day 3 只展示筛选 JSON。

`ping_research` 仍是健康检查，不读取行情。
