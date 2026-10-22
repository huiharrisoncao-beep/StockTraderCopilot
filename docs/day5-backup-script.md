# Day 5 备用讲解稿

这段给现场录 2–3 分钟视频用。我不能代替打开 Web UI 录屏，所以视频文件还没有生成。录的时候使用已经冻结的 fixture，不要重跑 `freeze-fixture`，也不要升级 `dsh`。

数据日期说 `2026-10-21`，不要说“今天的行情”。上证收盘只说工具或报告里的 `3713.03`。第一条候选只说 `300031`，收盘 `26.36`。

## 0:00–0:20

打开仓库里的报告 [reports/2026-10-21/research-20261022-082010.md](../reports/2026-10-21/research-20261022-082010.md)。先读标题下的 `data_date` 和末尾免责声明。说明这是历史样本，不是实时行情，也不是投资建议。

## 0:20–1:10

终端在仓库根目录执行，不配置模型：

```sh
cd /Users/harrisoncao/Workspace/StockTraderCopilot
PYTHONPATH=python .venv/bin/python -m trader.cli daily --universe demo --data-mode fixture --json
```

指出 JSON 里的 `ok: true`、`data_date`、候选第一名和 `report.markdown_path`。连续两次候选顺序一致。这一步不访问模型，代理不可用时也能出报告。

## 1:10–2:00

打开新生成的 Markdown。展示四张表：市场、候选行业分布、候选股票、重点研究。说明行业一节不是全市场板块排名。`valuation`、`news`、`fund_flow` 是空的，因为没有接入，不是“暂无利空”。

## 2:00–2:40

如果要演示失败，不要口头补指数。改说：实时接口没有返回可验证的数据，系统不会补造行情，下面用已经标注日期的历史样本。故障演练的实际错误码在 [day5-drill-log.md](day5-drill-log.md)。
