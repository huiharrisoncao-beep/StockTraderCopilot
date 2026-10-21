---
name: daily-stock-research
description: Run the A-share after-close research workflow once market, screening, and report tools exist.
disable-model-invocation: true
---

# A 股盘后研究

Day 1 占位。模型调用已关闭，避免在工具尚未接入时执行半成品流程。Day 3 接入 `get_market_snapshot` 和 `screen_stocks` 后再打开。

当前健康检查工具是 `ping_research`。用户明确要求 ping 研究插件时，调用它并原样转述返回的 JSON。
