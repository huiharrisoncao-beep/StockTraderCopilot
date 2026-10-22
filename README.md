# Stock Trader Copilot

用 DeepSeek Harness 定制的 A 股研究员工作流。设计说明见 [docs/stock-researcher-workflow-design.md](docs/stock-researcher-workflow-design.md)。

研究结果不是投资建议，也不会接入实盘下单。

## Day 1 核对

2026-10-21 在本机核对，后续实现以这些事实为起点。

| 项 | 值 |
|---|---|
| `dsh` | `0.2.1-rc.2`，`/Users/harrisoncao/.local/node-current/bin/dsh` |
| Node | `v24.14.0` |
| pnpm | `10.34.7` |
| Python | `3.13.9` |
| Harness home | `~/.dsh`。`DSH_HOME` 未设置 |
| 已有 Profile | `web`、`headless`、`desktop`，以及本次新建的 `trading-research` |
| 配置根 | `~/.dsh/profiles/<name>/cordis.yml` 是空入口列表，不要手改 |
| 用户补丁 | `~/.dsh/profiles/<name>/cordis.patch.yml` |

`desktop` Profile 不能用 CLI 启动。官方 `workflow` 工具运行的是模型当场编写的 JavaScript，没有已保存工作流文件，也没有检查点。量化步骤不要走它。业务工作流由 Profile、插件工具、`AGENTS.md` 和 Skill 共同定义。

## trading-research

Profile 从 `web` 模板复制，不改日常使用的 `web`。模板只包含 `@deepseek-ai/dsh-base` 和 `@deepseek-ai/dsh-web-app`。`--from-default-profile` 会替换同名 Profile，只在第一次创建或明确重置时使用。

```sh
dsh --profile trading-research --from-default-profile web --no-open --port 8787
```

插件安装命令已经跑通。pnpm 接受本地绝对路径，并记成 `link:` 依赖：

```sh
dsh plugin --profile trading-research add /Users/harrisoncao/Workspace/StockTraderCopilot/harness/plugins/stock-research
```

安装输出会警告包没有 `dsh.bundle`，因此它只是依赖，不是自动加载的配置层。加载靠 Profile patch 里的 `insert`。裸写 `- id` 只能覆盖已有行；不存在的 id 会报 `entry "stock-research" not found`。

可复制的 patch 在 [harness/patches/trading-research.patch.yml](harness/patches/trading-research.patch.yml)，并已写入 `~/.dsh/profiles/trading-research/cordis.patch.yml`。

启动：

```sh
cd /Users/harrisoncao/Workspace/StockTraderCopilot
dsh --profile trading-research --no-open --port 8787
```

`dsh --profile trading-research --help` 显示的是 web 应用自己的参数，这是预期行为。组合结果用：

```sh
dsh --profile trading-research --dump-config
```

## Day 1 验收

`ping_research` 留作健康检查。本地直接调用返回：

```json
{"ok":true,"tool":"ping_research","note":""}
```

Web UI 中让 Agent 只调用一次该工具。Trajectory 里的实际工具行是：

```text
ping_research {"note":"ping once as requested"}
→ {"ok":true,"tool":"ping_research","note":"ping once as requested"}
```

插件源码在 [harness/plugins/stock-research/src/index.ts](harness/plugins/stock-research/src/index.ts)。它从 `~/.dsh/profiles/node_modules/@deepseek-ai/dsh-tools` 动态加载 `defineTool`。因为 Profile 用的是指向仓库的符号链接，Node 会从仓库真实路径解析依赖，走不回 Profile 的 `node_modules`。

这次 Web 会话仍停在已有工作区 `DSSpace`。嵌入式目录选择器没有弹出，所以没有改 `~/.dsh/storages/workspace.json`。插件是 Profile 级的，这次调用不依赖工作区。Day 3 之前要在 UI 里把工作区加到本仓库，`AGENTS.md` 才会进入会话。

Skill 在 [.dsh/skills/daily-stock-research/SKILL.md](.dsh/skills/daily-stock-research/SKILL.md)，目前 `disable-model-invocation: true`。行情工具还没接，不能让模型按半成品流程执行。

## Day 2 数据与筛选

依赖已冻结在 [python/requirements.txt](python/requirements.txt)。本机曾把 `HTTP_PROXY` 指到 `127.0.0.1:10808`，`requests` 会被重置，而 `curl` / `httpx` 可以读到东方财富。AKShare 仍负责 URL、参数和列名；[python/trader/data/transport.py](python/trader/data/transport.py) 只替换传输，并把不稳定的 `48.push2` 改写到已核对的 `82.push2`。

2026-10-21 核对过的接口：

| 用途 | 函数 | 备注 |
|---|---|---|
| 前复权日线 | `ak.stock_zh_a_hist(..., adjust="qfq")` | 成交量单位是手 |
| 指数日线 | `ak.stock_zh_index_daily_em` | `sh000001`、`sz399001`、`sz399006` |
| 股票池 | `ak.stock_zh_a_spot_em` | 全市场分页或 `push2` 不通时，改用新浪按成交额排序的页面 |
| 日线回退 | `ak.stock_zh_a_hist_tx` | `push2his` 断开时使用。成交量单位是股，量比仍在同一单位内计算 |

`daily` 只读 fixture，不访问网络。现场抓取用 `freeze-fixture`，成功后再把 `data/fixtures/current.json` 指向新样本。

```sh
cd /Users/harrisoncao/Workspace/StockTraderCopilot
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
PYTHONPATH=python .venv/bin/python -m trader.cli freeze-fixture --limit 150 --json
PYTHONPATH=python .venv/bin/python -m trader.cli daily --universe demo --data-mode fixture --json
PYTHONPATH=python .venv/bin/python -m pytest tests -q
```

规则集是 `trend_volume_v1`。没有候选时 `ok` 仍为 `true`，`error` 为 `null`。`csi300` 在 Day 2 返回 `INVALID_ARGUMENT`。涨跌家数来自快照，不是交易所官方统计。

2026-10-21 23:30 冻结的样本是 [data/fixtures/demo-20261021](data/fixtures/demo-20261021)。当时东方财富 `push2` / `push2his` 断开，所以 manifest 记录的实际接口是 `stock_zh_a_hist_tx` 和一页新浪成交额排序。150 只股票全部抓到，最后交易日 `2026-10-21`，上证收盘 `3713.03`。成交量单位是股。连续两次 `daily` 的前十代码和顺序一致，第一条是 `300031`。涨跌家数范围是 `demo_universe`，不是全市场。

## Day 3 Harness

插件仍是一个包，注册 `ping_research`、`get_market_snapshot` 和 `screen_stocks`。工具不接收文件路径。数据模式来自 Profile patch，模型不能改。Python 使用仓库虚拟环境，避免系统 `python3` 没有依赖。

```sh
cd /Users/harrisoncao/Workspace/StockTraderCopilot
dsh --profile trading-research --no-open --port 8787
node --experimental-strip-types --test harness/plugins/stock-research/test/runner.test.mjs
```

固定提示词：

```text
加载 daily-stock-research。使用 fixture 数据，执行最近一个已冻结交易日的 A 股盘后研究。
只引用工具返回的数字。如果工具失败，停止并说明错误码。不要给出买卖指令。
```

插件入口已用与 DSH 相同的方式加载。三个工具都能注册；fixture 快照 `ok: true`，`data_date` 为 `2026-10-21`，上证收盘 `3713.03`；`screen_stocks` 按 `limit: 2` 切出 `300031`、`603626`。`dsh --dump-config` 能看到插件 `stock-research`。Profile 启动后才会在会话里挂上工具。

在 UI 里把工作区加到本仓库后，`AGENTS.md` 才会进入会话。

## Day 4 研究与报告

插件增加 `get_stock_research_data`、`check_stock_risk` 和 `generate_daily_report`。研究卡不产生观点。`valuation`、`news`、`fund_flow` 固定为空。风险检查只输出规则命中。报告由 Python 渲染，行业一节标题是“候选行业分布”。

```sh
PYTHONPATH=python .venv/bin/python -m trader.cli daily --universe demo --data-mode fixture --json
node --experimental-strip-types --test harness/plugins/stock-research/test/runner.test.mjs
```

`daily` 会在筛选后继续写研究卡、风险命中和 `reports/<data_date>/<run_id>.md`。模型失败时可以直接打开这个文件。免责声明固定为：研究结果仅用于演示研究流程，不构成投资建议，不保证收益，不触发任何交易。
