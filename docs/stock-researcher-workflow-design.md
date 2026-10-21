# 使用 DSH 定制股票研究员工作流平台

详细设计与实现说明 · Stock Trader Copilot

| 项 | 内容 |
|---|---|
| 文档状态 | 设计冻结稿（演示版） |
| 演示日期 | 2026-10-26（星期一） |
| 演示主题 | 使用 DSH 定制一个股票研究员的工作流平台 |
| 依据 | [stock_trader_copilot_implementation_plan-2.html](../stock_trader_copilot_implementation_plan-2.html) |
| 运行时基线 | 本机 `dsh 0.2.1-rc.2`，`$DSH_HOME` 未设置，实际 home 为 `~/.dsh` |
| 读者 | 演示讲者、实现者 |
| 合规边界 | 研究辅助，不是投资建议，不接入实盘下单 |

本文把实施计划落成可实现的设计。凡是依赖 DeepSeek Harness（下称 DSH）机制的地方，都以本机 `0.2.1-rc.2` 的 CLI 与已安装包说明为准，不假设存在原生 `workflow.yaml`。

---

## 1. 演示要讲清楚的一句话

股票研究员的日常不是“让模型猜一只股票”，而是一条可重复的研究流水线：看市场、看板块、按规则选股、做个股研究、做风险检查、留下可追溯的报告。

DSH 负责把这条流水线装进一个可启动的研究员运行时：Profile 决定这次加载什么，Bundle 组织能力，Plugin 把 Python 量化能力暴露成工具，Skill 与 `AGENTS.md` 约束研究员怎么用这些工具。Python 负责算，模型负责解释，人负责决定。模型不允许心算价格、均线和收益率。

---

## 2. 目标、非目标与成功定义

### 2.1 产品定义

**股票研究员工作流平台**：一个用 DSH 定制出来的研究工作台。交易员或研究员用一句话启动盘后研究，系统读取真实行情或已标注的历史样本，完成确定性筛选，再由模型根据工具返回值撰写研究报告。

它不是自动交易系统，也不是收益预测模型。

### 2.2 成功定义

演示成功，当且仅当下面六件事同时成立：

1. 用一个 Profile 启动定制后的研究员运行时。
2. Agent 调用项目自己的工具，而不是在对话里编造行情。
3. 行情来自 AKShare 或一份明确标注日期与来源的本地样本。
4. MA20、MA60、20 日收益率、成交量比率由 Python 计算。
5. 产出 Markdown 报告和同内容的 JSON，报告里写明数据日期、来源和缺失项。
6. 任一环节失败时，系统报错或降级，不生成虚构行情，不自动下单。

### 2.3 优先级

| 级别 | 范围 | 演示日要求 |
|---|---|---|
| P0 | Profile 可启动；至少一个自定义工具被调用；行情可读；指标与筛选；Markdown + JSON 报告 | 必须完成 |
| P1 | 多步工作流稳定复现；市场环境；个股研究；风险检查；简单历史回测 | 尽量完成，回测可独立 |
| P2 | 自动下单、实时盯盘、复杂多 Agent、Web 业务前端、机器学习预测 | 明确不做 |

P2 里的“Web 业务前端”指自研交易界面。演示可以使用 DSH 自带的 `web` Profile UI，那是 Harness 宿主，不是业务前端。

### 2.4 设计原则

| 原则 | 含义 |
|---|---|
| Python 负责计算 | 清洗、指标、筛选、风险规则、回测都是确定性函数 |
| Harness 负责编排入口 | Profile、Bundle、Plugin、Skill、工具调用、会话 |
| 模型负责解释 | 只解释工具已经返回的结构化结果 |
| 人负责决策 | 报告中的观察条件不是委托指令 |
| 失败可见 | 缺数据就标缺失，接口失败就停在该步，不补造数字 |
| 先冻结技术 | 不在演示周更换数据源、框架或模型供应商 |

---

## 3. 本机 DSH 事实基线

2026-10-21 在本机核实，后续实现以这些事实为起点。若升级 DSH，必须重做本节核对，不能沿用本文的包名假设。

| 事实 | 值 |
|---|---|
| CLI | `/Users/harrisoncao/.local/node-current/bin/dsh` |
| 版本 | `0.2.1-rc.2` |
| Node | `v24.14.0` |
| Python | `3.13.9` |
| Harness home | `~/.dsh`（`DSH_HOME` 未设置） |
| 已有 Profile | `web`、`headless`、`desktop` |
| `desktop` | CLI 拒绝启动和 dump，留给 Desktop 应用 |
| 配置根 | Profile 的 `cordis.yml` 是空入口列表，不要手改 |
| 用户补丁 | `~/.dsh/profiles/<name>/cordis.patch.yml` |
| 组合声明 | `package.json` 的 `dsh.profile.bundles` |

当前 `web` Profile 的 bundle 顺序：

1. `@deepseek-ai/dsh-base`
2. `@deepseek-ai/dsh-web-app`
3. `@deepseek-ai/dsh-experimental-plugin-market-bundle`
4. `dshmarket`

配置层从空根开始，按这个顺序叠加：

1. `dsh.profile.bundles` 里每个 bundle 的 patch
2. Profile 自己的 `cordis.patch.yml`
3. `~/.dsh/cordis.patch.yml`（若存在）
4. 命令行 `--patch` 覆盖层

因此：**业务工作流不是 DSH 的一种文件格式，而是“能力组合 + 工具 + 研究员指令”共同定义的执行方式。**

### 3.1 四个扩展点分别是什么

| 扩展点 | 本机机制 | 在本项目中的用法 |
|---|---|---|
| Profile | `$DSH_HOME/profiles/<name>`，可用 `dsh --profile <name>` 启动 | 新建 `trading-research`，从 `web` 模板复制，不改日常使用的 `web` |
| Bundle | npm 包，在 `package.json` 里用 `dsh.bundle.patch` 指向一份 patch | 演示周不做三个官方风格 bundle；用一份本地 patch 插入插件。名称 `trader-market` / `trader-quant` 留作后续拆分 |
| Plugin | Cordis 插件：导出 `name`、`apply`、`inject`，可选 Schemastery `Config` | 一个插件注册全部研究工具，内部再按模块拆分 |
| Workflow 工具 | `@deepseek-ai/dsh-workflow` + `@deepseek-ai/dsh-tool-workflow` | **不作为量化主路径**。它运行的是模型当场编写的 JavaScript，用来把工作扇出给 subagent |

官方 workflow 能力的当前限制，决定了它不能当研究平台的状态机：

- 没有已保存的工作流文件，也不会因为目录里有 Markdown 就自动执行。
- 不支持嵌套 `workflow()`。
- 没有检查点，进程重启后不能续跑。
- 子 agent 失败时 `agent()` 返回 `null`，由脚本自行处理。
- 官方说明：一两项委派优先用普通工具或 subagent；只有明确的大扇出任务才用 `workflow` 工具。

所以本项目采用实施计划里的方案 C，并把它落到本机机制上。

### 3.2 方案选择

| 方案 | 做法 | 结论 |
|---|---|---|
| A | 只写 `workflows/daily-stock-research.md`，指望 DSH 自动执行 | 不采用。该文件不会自动执行 |
| B | Python 固定顺序跑完全程，DSH 只暴露一个入口工具 | 作为失败兜底和无模型验收路径保留 |
| C | Python 做计算，Plugin 暴露工具，Skill/`AGENTS.md` 约束步骤，Profile 装载能力 | **采用** |

Markdown 工作流文件仍然要写，但它的角色是 Skill 正文和演示讲稿，不是运行时格式。

---

## 4. 总体架构

```text
研究员
  │  “执行最近一个交易日的 A 股盘后研究”
  ▼
dsh --profile trading-research
  │
  ├─ Profile trading-research
  │    └─ bundles: dsh-base + dsh-web-app + 市场 bundle + 本项目 patch
  │
  ├─ AGENTS.md
  │    └─ 研究员宪法：禁止编造行情、禁止下单、必须引用工具结果
  │
  ├─ Skill: daily-stock-research
  │    └─ 何时启动、步骤顺序、失败时怎么说
  │
  ├─ Plugin: stock-research
  │    ├─ get_market_snapshot
  │    ├─ screen_stocks
  │    ├─ get_stock_research_data      (P1)
  │    ├─ check_stock_risk              (P1)
  │    ├─ generate_daily_report
  │    └─ run_daily_research            (确定性兜底)
  │
  └─ 模型
       └─ 只解释工具 JSON，组织报告语言

Plugin
  │  子进程，工作目录固定，超时，只解析 stdout JSON
  ▼
python -m trader.cli <command> --json
  │
  ├─ data/         AKShare 或 fixture
  ├─ indicators/   MA、收益率、量比、阶段高点
  ├─ screening/    规则筛选
  ├─ research/     个股数据包
  ├─ risk/         完整性、趋势走弱、波动、行业集中
  ├─ reporting/    Markdown + JSON
  └─ store/        SQLite
```

演示时要让观众看到两次边界：

1. **宿主边界**：DSH 不知道均线公式，它只知道有哪些工具、参数和研究员指令。
2. **计算边界**：Python 不知道怎么写研报措辞，它只返回可复核的数字和规则命中原因。

### 4.1 为什么不把每个指标做成工具

`ma20()`、`return_20d()`、代码格式转换、缺失值处理都是内部函数。暴露它们会让模型分多次取数再自己拼表，既慢又容易把不同日期的数字拼在一起。工具粒度是“一次研究动作”，不是“一个数学函数”。

### 4.2 为什么保留 `run_daily_research`

演示主路径是 Agent 分步调用工具，这样能展示 Harness。验收和断网彩排另有一条 Python 入口：同一步骤、同一份 JSON 契约、不经过模型。模型 API 失败时，这条路径仍能交出量化结果，报告里的“解释”段标记为未生成。

---

## 5. DSH 定制设计

### 5.1 Profile：`trading-research`

不修改 `~/.dsh/profiles/web`。演示环境坏了也不能影响日常 Profile。

创建方式以 CLI 为准：

```sh
dsh --profile trading-research --from-default-profile web --no-open --port 8787
```

`--from-default-profile` 会用模板的新副本替换同名自定义 Profile。只在 Profile 尚不存在，或明确要重置时使用。重置前先复制已改过的 `cordis.patch.yml`。

创建后的目录：

```text
~/.dsh/profiles/trading-research/
├── package.json          # dsh.profile.bundles
├── cordis.yml            # 保持空列表，不手改
├── cordis.patch.yml      # 插入研究插件、默认模型、研究员相关配置
├── pnpm-workspace.yaml
└── node_modules/
```

演示启动命令冻结为：

```sh
dsh --profile trading-research --no-open --port 8787
```

工作目录必须是本仓库根目录，这样 `AGENTS.md`、`.dsh/skills` 和相对数据路径才能被发现。

```sh
cd /Users/harrisoncao/Workspace/StockTraderCopilot
dsh --profile trading-research --no-open --port 8787
```

可选的无 UI 验收 Profile `trading-research-headless` 从 `headless` 模板复制，安装同一个插件。它不是演示主路径，避免把范围扩成两套 UI。Headless 验收命令形态：

```sh
dsh --profile trading-research-headless --json "使用 daily-stock-research，对 fixture 数据执行盘后研究，不要访问网络"
```

该命令只在 headless Profile 已装上同一插件后才有意义。演示日不以它为唯一路径。

### 5.2 能力怎么装进去

演示周用 **一个本地插件 + 一段 patch**，不先拆三个 bundle。拆 bundle 不增加研究正确性，却增加安装失败点。

计划中的三个名字保留为模块边界，而不是三个 npm 包：

| 计划中的名字 | 演示周的落点 |
|---|---|
| `trader-base` | `AGENTS.md` + Skill，规定角色、禁止项、报告结构 |
| `trader-market` | `get_market_snapshot` 与其 Python 模块 |
| `trader-quant` | 筛选、研究、风险、报告工具 |

后续若要分发，再把 patch 收成 bundle 包。官方 bundle 的形状是：

```json
{
  "name": "@local/trader-quant",
  "private": true,
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

然后把包名追加到 Profile 的 `dsh.profile.bundles` 末尾。演示周不阻塞在这一步。

### 5.3 Plugin：`stock-research`

插件是 Cordis 插件，运行在 Node 里。它不实现指标。它只做四件事：校验参数、拉起 Python、解析 JSON、把结构化结果交回工具注册表。

对照本机 `@deepseek-ai/dsh-tool-todo` 的插件形状，最小导出是：

```js
export const name = "stock-research";
export const inject = ["tools"];

export function apply(ctx, config) {
  ctx.tools.register(defineTool({ /* ... */ }));
}
```

`inject: ["tools"]` 表示没有工具注册表时插件不要假装可用。`defineTool` 来自 `@deepseek-ai/dsh-tools`。参数用该包的 schema DSL，执行函数只返回声明过的 JSON。

配置走插件 config，不把仓库绝对路径写死在源码里：

```yaml
- id: stock-research
  name: "@stock-trader/dsh-plugin"
  config:
    python: "python3"
    module: "trader.cli"
    projectRoot: "/Users/harrisoncao/Workspace/StockTraderCopilot"
    dataMode: "fixture"
    timeoutMs: 120000
```

`dataMode` 演示当天默认 `fixture`。现场网络确认可用后，再在设置或 patch 里改成 `live`。不要在演示前五分钟改默认值。

插件调用约定：

- 工作目录固定为 `projectRoot`，忽略模型传入的路径。
- 命令形如 `python3 -m trader.cli <command> --json`，附加白名单参数。
- 不使用 `shell: true`，参数数组直接传给 `spawn`。
- stdout 必须是单一 JSON 对象。stderr 只进日志，不进模型可见正文，避免把堆栈当成行情。
- 超时、非零退出、JSON 解析失败，都返回 `ok: false`，不抛到 Agent 循环外面把整轮打崩。
- 工具结果里不包含 API Key、本机用户名以外的 home 路径可以保留项目相对路径。

模型不允许通过这个插件传入任意 shell。股票代码只接受 `6` 位数字，或 `SH`/`SZ`/`BJ` 前缀加 `6` 位数字。宇宙名称只接受枚举：`demo`、`csi300`。

### 5.4 研究员宪法：`AGENTS.md`

`dsh-base` 已包含 `@deepseek-ai/dsh-agent-instructions`。会话工作目录位于本仓库时，会加载仓库根目录的 `AGENTS.md`。这是研究员角色的持久约束，比单次提示词可靠。

`AGENTS.md` 必须写清：

- 角色是 A 股研究助手，不是投资顾问，不输出“买入”“卖出”“目标价”“仓位建议”作为指令。
- 可以输出“观察条件”，并明确那不是委托。
- 价格、涨跌、成交额、指标、筛选结果只能来自工具 JSON。
- 工具失败时说明失败步骤和 `error.code`，禁止用记忆或常识补数。
- 数据日期不是“今天”，而是工具返回的 `data_date`。若 `data_date` 不是最近一个已完成交易日，要在报告开头说明。
- 不得调用或建议任何下单、转账、登录券商的操作。
- 候选为空是合法结果，写明规则和样本范围即可。

### 5.5 Skill：`daily-stock-research`

文件系统 Skill 会被 `@deepseek-ai/dsh-skill-filesystem` 扫描。项目内路径使用：

```text
.dsh/skills/daily-stock-research/SKILL.md
```

也兼容 `.agents/skills`。演示只用 `.dsh/skills`，避免两份正文漂移。

Frontmatter 至少包含 `name` 与 `description`。正文写步骤，不写指标公式的第二份实现。公式只存在于 Python。

Skill 步骤：

1. 调用 `get_market_snapshot`。失败则停止，不进入选股。
2. 用同一次运行的 `data_date` 调用 `screen_stocks`。不得改日期来“找一个更好看的结果”。
3. 若有候选，对最多 5 只调用 `get_stock_research_data` 和 `check_stock_risk`。P0 若这两个工具未完成，改为把筛选结果里的命中原因直接写入报告，并注明个股研究未展开。
4. 调用 `generate_daily_report`，把前面工具的 JSON 路径或对象交给它。模型可以润色语言，不能改写数字。
5. 向用户展示报告路径、数据日期、来源和警告列表。

`disable-model-invocation` 保持默认，允许模型在用户提到“盘后研究”“每日研究”“选股报告”时加载该 Skill。

### 5.6 原生 `workflow` 工具的使用边界

演示可以花 30 秒说明它的存在，说明本项目为什么不用它做主路径。不要在演示里临时让模型编写一段选股 JavaScript。那会把“确定性计算”这个论点打穿。

若 P1 之后要做“同一候选股的多角度文字研究”，可以让 `workflow` 脚本并行调用已经存在的研究工具，脚本本身仍然禁止算术。这不是演示周任务。

### 5.7 模型配置

沿用 Profile 里已有的模型行，不在演示周引入第二个供应商。本机 `web` patch 中可见的默认形态是：

```yaml
- id: agent-default-model
  name: "@deepseek-ai/dsh-agent-default-model"
  config:
    provider: deepseek-official
    model: deepseek-flash
    reasoningEffort: high
```

复制模板后要核对 `trading-research` 的实际 `id` 和字段，以 `dsh --profile trading-research --dump-config` 为准。演示使用已登录的 DeepSeek 凭据，凭据留在 `~/.dsh` 的凭证文件，不写入仓库。

---

## 6. 业务工作流

### 6.1 主流程

```text
启动 trading-research
  → 加载 AGENTS.md 与 Skill
  → get_market_snapshot
  → screen_stocks
  → 对 Top N 做 get_stock_research_data
  → check_stock_risk
  → generate_daily_report
  → 展示 reports/<data_date>/daily-research.md
```

每一步的输入都带上一步返回的 `run_id` 和 `data_date`。不允许工具隐式使用“此刻的系统日期”作为行情日期。系统日期只用于文件名里的生成时间。

### 6.2 步骤契约

| 步骤 | 工具 | 输入 | 输出 | 失败行为 |
|---|---|---|---|---|
| 市场 | `get_market_snapshot` | `universe`，可选 `as_of` | 指数、涨跌家数、成交额、`data_date`、来源 | 停止全流程 |
| 选股 | `screen_stocks` | `run_id`，`data_date`，`universe` | 候选列表、规则、被排除数量 | 停止；空列表不是失败 |
| 个股 | `get_stock_research_data` | `run_id`，代码列表，最多 5 | 趋势、动量、量能、行业、缺失字段 | 单票失败则剔除该票并记录 |
| 风险 | `check_stock_risk` | `run_id`，候选 | 数据完整性、走弱、异常波动、行业集中 | 风险工具失败时报告仍可生成，但必须把风险段标成未完成 |
| 报告 | `generate_daily_report` | `run_id` | Markdown 路径、JSON 路径、警告 | 保留中间 JSON，允许重试这一步 |

### 6.3 运行标识

每次研究生成一个 `run_id`，格式 `research-YYYYMMDD-HHMMSS`。它贯穿工具、SQLite 和报告文件名。重试报告生成复用同一个 `run_id`，不重新选股，避免前后数字不一致。

---

## 7. Python 实现设计

### 7.1 模块

```text
python/trader/
├── __init__.py
├── cli.py                 # 唯一进程入口
├── contracts.py           # JSON 信封与错误码
├── data/
│   ├── source.py          # live / fixture 选择
│   ├── akshare_source.py
│   ├── fixture_source.py
│   └── quality.py         # 缺失、重复日期、量异常、复权口径
├── indicators/
│   └── trend.py           # MA、收益率、量比、阶段高点
├── screening/
│   ├── rules.py
│   └── screener.py
├── research/
│   └── stock_brief.py
├── risk/
│   └── checks.py
├── reporting/
│   └── daily_report.py
└── store/
    └── sqlite_store.py
```

依赖冻结在 `python/requirements.txt`：`akshare`、`pandas`、`numpy`。演示周不引入回测框架。P1 回测用同一份日线在 Pandas 里计算，单独模块 `backtest/rule_backtest.py`，不接入主路径也可以。

### 7.2 CLI

```text
python -m trader.cli market-snapshot --universe demo --data-mode fixture --json
python -m trader.cli screen --run-id <id> --data-date YYYY-MM-DD --universe demo --json
python -m trader.cli research --run-id <id> --codes 600519,000858 --json
python -m trader.cli risk --run-id <id> --json
python -m trader.cli report --run-id <id> --json
python -m trader.cli daily --universe demo --data-mode fixture --json
```

`--json` 时成功和失败都向 stdout 打印一个对象，进程退出码仍区分：成功 `0`，业务失败 `2`，用法错误 `1`。插件两种都解析，不依赖退出码猜测正文。

### 7.3 统一 JSON 信封

所有工具和 CLI 使用同一信封。模型被指示只引用 `data` 内的字段。

```json
{
  "ok": true,
  "tool": "screen_stocks",
  "run_id": "research-20261023-183000",
  "data_date": "2026-10-23",
  "generated_at": "2026-10-23T18:30:02+08:00",
  "source": {
    "provider": "fixture",
    "dataset": "data/fixtures/demo-20261023",
    "adjustment": "qfq",
    "note": "本地历史样本，不是实时行情"
  },
  "warnings": [],
  "error": null,
  "data": {}
}
```

失败时：

```json
{
  "ok": false,
  "tool": "get_market_snapshot",
  "run_id": null,
  "data_date": null,
  "generated_at": "2026-10-26T09:00:00+08:00",
  "source": { "provider": "akshare", "dataset": null, "adjustment": "qfq" },
  "warnings": [],
  "error": {
    "code": "DATA_SOURCE_UNAVAILABLE",
    "message": "AKShare 指数行情请求失败",
    "retryable": true
  },
  "data": null
}
```

错误码封闭集合：

| code | 含义 | 模型应如何说 |
|---|---|---|
| `DATA_SOURCE_UNAVAILABLE` | 行情接口失败 | 本步失败，没有市场数据 |
| `DATA_QUALITY_FAILED` | 重复日期、空表、日期倒挂 | 数据不可用，不继续选股 |
| `MISSING_FIELDS` | 单票缺字段 | 剔除或标注，不估算 |
| `EMPTY_UNIVERSE` | 股票池为空 | 配置错误，不是“市场没有机会” |
| `NO_CANDIDATES` | 规则下候选为空 | 合法结果，展示规则 |
| `INVALID_ARGUMENT` | 代码或宇宙不合法 | 不重试乱猜参数 |
| `REPORT_WRITE_FAILED` | 报告写盘失败 | 指出已保留的中间 JSON |
| `TIMEOUT` | Python 超时 | 不把部分 stdout 当结果 |
| `INTERNAL` | 未分类异常 | 保留 stderr 摘要，不展开堆栈给观众 |

`NO_CANDIDATES` 的 `ok` 仍为 `true`。它不是异常。空候选放在 `data.candidates: []`。

### 7.4 数据源

两种来源实现同一个接口：`load_universe()`、`load_daily_bars()`、`load_index_snapshot()`、`load_industry()`。

| 模式 | 行为 |
|---|---|
| `fixture` | 只读 `data/fixtures/<dataset>/`。文件名和 `manifest.json` 写明最后交易日 |
| `live` | 调 AKShare。成功后把原始响应落到 `data/raw/<data_date>/`，清洗结果落到 `data/processed/` |

`manifest.json`：

```json
{
  "dataset": "demo-20261023",
  "provider": "akshare",
  "captured_at": "2026-10-23T18:10:00+08:00",
  "data_date": "2026-10-23",
  "adjustment": "qfq",
  "universe": "demo",
  "symbols": 180,
  "is_live": false,
  "note": "截至该交易日收盘的历史样本"
}
```

演示日不要把 fixture 说成实时行情。开场白使用：“下面使用截至最近一个已完成交易日的样本；系统会在报告里打印这个日期。”

AKShare 接口在 Day 2 验证后再写死函数名。设计上把接口名收口到 `akshare_source.py` 的三个函数，验证失败时只改这一层。不在筛选器里直接 `import akshare`。

### 7.5 数据质量

进入指标计算前必须通过：

- 交易日唯一，禁止同一代码同一日期两行。
- 日期升序，时区统一到 `Asia/Shanghai` 的日期，不带盘中时间。
- `close`、`volume` 为有限正数；停牌日成交量为 0 时保留，但不参与“放量”判定。
- 复权口径固定前复权 `qfq`。未确认复权时，该票标记 `adjustment_unconfirmed` 并排除出候选，不混入口径。
- 上市不足 60 个交易日的股票不计算 MA60，直接排除，原因写 `INSUFFICIENT_HISTORY`。
- 缺失行业时仍可入选，风险段标记行业未知，不发明行业。

质量失败是全市场失败还是单票失败，按范围区分：指数快照失败则停止；单票日线失败则剔除该票。

### 7.6 指标

只实现演示要用的四个，全部向量化，禁止在模型侧重算。

| 指标 | 定义 | 备注 |
|---|---|---|
| `ma20` | 最近 20 个交易日收盘价简单平均 | 含当日 |
| `ma60` | 最近 60 个交易日收盘价简单平均 | 含当日 |
| `return_20d` | `close / close.shift(20) - 1` | 不是自然日 |
| `volume_ratio` | `volume / volume.rolling(20).mean()` | 当日量为 0 时结果为 0 |
| `high_60d` | 最近 60 日最高价 | 辅助展示，不单独作为工具 |
| `distance_to_high_60d` | `close / high_60d - 1` | 负数表示低于阶段高点 |

窗口用交易日根数，不用 `timedelta(days=20)`。

### 7.7 筛选规则

规则必须可配置，默认值写在 `python/trader/screening/rules.py`，并随结果输出，避免演示时口头规则和代码不一致。

默认规则，名称 `trend_volume_v1`：

| 规则 | 条件 | 排除原因码 |
|---|---|---|
| 历史足够 | 有效交易日 ≥ 60 | `INSUFFICIENT_HISTORY` |
| 多头排列 | `close > ma20 > ma60` | `TREND_NOT_ALIGNED` |
| 动量区间 | `0.05 ≤ return_20d ≤ 0.40` | `RETURN_OUT_OF_RANGE` |
| 放量但非极端 | `1.2 ≤ volume_ratio ≤ 3.0` | `VOLUME_OUT_OF_RANGE` |
| 数据干净 | 无缺失收盘价、口径已确认 | `DATA_INCOMPLETE` |

这些阈值是演示用的可解释规则，不是经过验证的交易策略。报告和讲者必须这样说。

排序：`return_20d` 降序，取前 10 作为候选，前 5 进入个股研究。并列时按代码升序，保证重复运行稳定。

宇宙：

- `demo`：仓库内 100–180 只流动性较好的股票清单，Day 2 生成后冻结。
- `csi300`：P1。演示不筛全市场，避免接口超时。

### 7.8 个股研究数据包

`get_stock_research_data` 不产生观点。它把筛选行展开成研究卡片：

- 代码、名称、行业（可空）
- `data_date`、收盘价、MA20、MA60、`return_20d`、`volume_ratio`、`distance_to_high_60d`
- 命中的规则版本
- 近 20 日收盘是否多数位于 MA20 之上：`closes_above_ma20_ratio`
- 缺失字段列表
- 明确为空的字段：`valuation`、`news`、`fund_flow`。演示周不接这些源，留空而不是写“暂无利空”

模型只能基于这些字段写“趋势结构、量能、缺失信息”。不能补充工具没给的财务数据。

### 7.9 风险检查

`check_stock_risk` 输出规则命中，不输出风险评分黑盒。

| 检查 | 判定 | 严重级别 |
|---|---|---|
| 数据完整性 | 研究卡缺价格或指标 | `block`，从重点研究移除 |
| 趋势走弱 | `close < ma20`，或 `ma20` 低于 5 个交易日前的 `ma20` | `warn` |
| 异常波动 | 20 日收益率绝对值大于 40%，或单日涨跌幅绝对值大于 9% 出现在窗口内 | `warn` |
| 行业集中 | Top 5 中同一行业 ≥ 3，且行业非空 | `warn` |
| 样本过期 | `data_date` 距离生成日超过 5 个自然日 | `warn`，提醒不是最新交易日 |

`block` 改变候选展示；`warn` 只进入报告风险段。不要把警告翻译成“建议卖出”。

### 7.10 报告

`generate_daily_report` 由 Python 渲染骨架，保证数字来自 JSON。模型如果要润色，只能改写已经生成的 Markdown 中的解释性段落，并保留 HTML 注释锚点之间的表格。

更稳的演示实现：Python 生成完整报告，模型在对话里摘要，不回写数字段。这样即使模型发挥，文件里的表仍可复核。

报告路径：

```text
reports/<data_date>/<run_id>.md
reports/<data_date>/<run_id>.json
```

结构与实施计划一致：

```text
# A 股盘后研究报告

## 一、报告信息与数据日期
## 二、市场环境
## 三、强势板块
## 四、候选股票与筛选依据
## 五、重点个股研究
## 六、观察条件
## 七、风险提示与失效条件
## 八、数据来源与质量说明
## 九、下一交易日观察清单
```

相对计划原文，第六章从“交易计划与触发条件”改成“观察条件”。演示平台不生成委托计划。观察条件只允许复述规则，例如“若后续收盘跌破 MA20，则不再满足 `trend_volume_v1`”。这是规则失效描述，不是交易指令。

板块一节：P0 若没有独立板块行情，就按候选股已有行业做计数，并写明“这是候选集中的行业分布，不是全市场板块涨幅排名”。不要把行业计数说成强势板块。P1 再接板块涨跌接口；接口未验证前，标题用“候选行业分布”。

每份报告末尾固定免责声明：研究结果仅用于演示研究流程，不构成投资建议，不保证收益，不触发任何交易。

### 7.11 SQLite

文件：`data/trader.sqlite`。演示规模不需要 PostgreSQL。

| 表 | 作用 | 主键 |
|---|---|---|
| `runs` | 一次研究的状态、数据日期、来源、模式 | `run_id` |
| `snapshots` | 市场快照 JSON | `run_id` |
| `bars` | 清洗后的日线，可只存本次宇宙 | `(symbol, trade_date, adjustment)` |
| `screen_hits` | 候选及排除统计 | `(run_id, symbol)` |
| `risk_flags` | 风险命中 | `(run_id, symbol, code)` |
| `reports` | 报告路径与生成状态 | `run_id` |

JSON 文件是演示时给人看的副本，SQLite 是追溯副本。两者都写。写报告失败时，`runs` 和 `screen_hits` 必须已经提交。

### 7.12 回测（P1，可独立）

若时间允许，对 `trend_volume_v1` 在 fixture 区间做描述性统计：每周最后一个交易日选前 10，记录其后 5 个交易日收益率的分布。输出样本数、中位数、胜率，并写明：

- 有生存者偏差和前视偏差风险，实现时信号日只用当日及以前数据。
- 不扣费、不建模冲击成本。
- 结果不是策略业绩承诺。

回测不进入星期一主演示，除非周六已经稳定。否则讲“后续规划”即可。

---

## 8. 工具参数

参数只暴露业务选择，不暴露文件路径。路径由插件配置决定，避免模型读任意文件。

### `get_market_snapshot`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `universe` | `demo` \| `csi300` | 是 | 默认调用用 `demo` |
| `as_of` | string | 否 | `YYYY-MM-DD`；省略时用数据源最后完整交易日 |

### `screen_stocks`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | string | 是 | 上一步返回 |
| `rule_set` | string | 否 | 默认 `trend_volume_v1` |
| `limit` | integer | 否 | 1–10，默认 10 |

`data_date` 不让模型另传，从 `run_id` 读取，防止日期被换掉。

### `get_stock_research_data`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | string | 是 | |
| `symbols` | string[] | 否 | 省略时取筛选前 5；最多 5；必须属于本次候选 |

### `check_stock_risk`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | string | 是 | 检查本次候选，不接受任意代码 |

### `generate_daily_report`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | string | 是 | 只渲染已落库的结果 |

### `run_daily_research`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `universe` | `demo` \| `csi300` | 是 | 内部按固定顺序调用上述函数 |

该工具的描述要写明：仅当用户要求“一次性跑完且不要分步”或分步工具失败后需要确定性重跑时使用。演示主路径不优先调用它。

---

## 9. 异常与降级

| 异常 | 系统行为 | 演示时怎么说 |
|---|---|---|
| 行情接口失败 | `DATA_SOURCE_UNAVAILABLE`，不生成数字 | 切换到已准备的 fixture 再跑一次，并说明这是历史样本 |
| 单票缺失 | 排除并记录原因 | 展示排除统计，证明没有把坏数据算进去 |
| 模型 API 失败 | Python 结果已在 `reports/` 或 `data/processed/` | 打开已生成的 Markdown，说明解释层没有覆盖计算层 |
| 候选为空 | `ok: true`，空列表，写明规则 | 这是规则结果，不是系统失败 |
| 报告写盘失败 | 保留 SQLite 和中间 JSON | 修复路径后只重跑 `generate_daily_report` |
| 插件超时 | `TIMEOUT`，丢弃不完整 stdout | 不展示半截 JSON |

现场备用顺序：

1. 首选：`dataMode=fixture` 的完整分步工具调用。
2. 次选：`python -m trader.cli daily --data-mode fixture --json`，然后打开报告。
3. 末选：播放周日录制的 2–3 分钟视频。视频里的日期必须和报告上的 `data_date` 一致。

不要在演示机器上临时 `pip install`、`npm update` 或升级 `dsh`。

---

## 10. 安全与合规

- 仓库不提交 `.env`、`~/.dsh/.credentials.yaml`、AKShare 或模型密钥。`.env.example` 只列变量名。
- 插件不接收任意命令、任意 URL、任意文件路径。
- 不注册券商、下单、银证转账、条件单工具。后续“模拟交易”也要单独设计，不在本次 Profile 里预留空工具。
- 报告和 UI 摘要都带“非投资建议”声明。
- 日志不打印凭证文件内容。Python 异常信息写入 `data/logs/<run_id>.log`，给模型的 `error.message` 使用固定短句。
- fixture 若来自真实历史行情，保留来源和抓取时间；不要改数字让图表更好看。

---

## 11. 仓库结构

```text
StockTraderCopilot/
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
├── .dsh/skills/daily-stock-research/SKILL.md
├── workflows/daily-stock-research.md      # 给人读的流程说明，不是 DSH 格式
├── harness/
│   ├── plugins/stock-research/            # Node 插件包
│   │   ├── package.json
│   │   └── src/index.ts
│   └── patches/trading-research.patch.yml # 可被 --patch 叠加，也可并入 Profile
├── python/
│   ├── requirements.txt
│   └── trader/
├── data/
│   ├── universe/demo.csv
│   ├── fixtures/demo-YYYYMMDD/
│   ├── raw/
│   ├── processed/
│   └── trader.sqlite
├── reports/
└── tests/
    ├── test_indicators.py
    ├── test_screener.py
    ├── test_risk.py
    ├── test_report.py
    └── test_cli_contract.py
```

`.gitignore` 忽略 `data/raw/`、`data/processed/`、`data/*.sqlite`、`reports/`、`.env`、`__pycache__/`。`data/fixtures/` 和 `data/universe/` 提交，保证断网可演示。

---

## 12. 实现计划

日期按实施计划。每天结束都要有可重复命令，而不是只打开过一次的会话。

### Day 1 · 10 月 21 日 · 骨架与 Harness 核对

已完成的核对应写入 README，避免第二天重新摸索：版本、home、Profile 列表、`cordis.yml` 不要手改、workflow 工具不是业务状态机。

仍须完成：

1. 初始化 Git 仓库。
2. 创建本文目录结构的空包和 `python/requirements.txt`。
3. 创建 `trading-research` Profile。创建后立刻执行：

```sh
dsh --profile trading-research --dump-config
dsh --profile trading-research --help
```

4. 确认插件安装命令。预期形态：

```sh
dsh plugin --profile trading-research add /absolute/path/to/harness/plugins/stock-research
```

若本机 pnpm 不接受本地路径，改用 `file:` 依赖并记录实际命令。不要改用未经验证的注册 API。

5. 插件先注册一个无业务意义的 `ping_research`，返回 `{ "ok": true, "tool": "ping_research" }`。在 Web UI 里让 Agent 调用它。成功后再删掉或留作健康检查。

验收：Profile 能启动；dump 里能看到插件；Agent 能调用 `ping_research`。

### Day 2 · 10 月 22 日 · 数据与量化

1. 用 AKShare 拉演示宇宙的日线和指数快照，核对字段名、复权口径、最后交易日。
2. 把成功响应冻结为 fixture，写 `manifest.json`。
3. 实现指标、质量检查、`trend_volume_v1`。
4. 单元测试不访问网络。
5. 一条命令输出候选 JSON：

```sh
python -m trader.cli daily --universe demo --data-mode fixture --json
```

验收：重复运行两次，候选代码和顺序一致；故意删掉一只股票的收盘价，该票被排除且原因码正确。

### Day 3 · 10 月 23 日 · 接入 Harness

1. 用真实工具替换 `ping_research` 的演示角色：先接 `get_market_snapshot`，再接 `screen_stocks`。
2. 统一信封。插件测试用 fixture 模式，不在插件开发时打到外网。
3. 写 `AGENTS.md` 和 Skill。
4. 在 UI 中用一句固定提示词跑通前两步，保存会话截图或导出文本。

固定提示词：

```text
加载 daily-stock-research。使用 fixture 数据，执行最近一个已冻结交易日的 A 股盘后研究。
只引用工具返回的数字。如果工具失败，停止并说明错误码。不要给出买卖指令。
```

验收：会话里能看到工具名、`data_date` 和候选表；断开模型时，CLI 仍能生成 JSON。

### Day 4 · 10 月 24 日 · 研究与报告

1. 实现个股数据包、风险检查、报告渲染。
2. 报告中的行业节使用“候选行业分布”措辞，除非板块接口已经单独验证。
3. 把 Skill 步骤补全到报告。
4. 核对免责声明、来源、缺失项。

验收：从 Harness 走完主路径，`reports/<data_date>/<run_id>.md` 与 `.json` 同时存在，表中的收盘价能在 fixture CSV 里找到。

### Day 5 · 10 月 25 日 · 故障演练

至少演练五次，并记下实际输出，不只写“已测试”：

1. fixture 路径改错，期望 `DATA_SOURCE_UNAVAILABLE` 或 `DATA_QUALITY_FAILED`。
2. 删掉一只候选的指标字段，期望该票被剔除。
3. 把规则临时改到不可能满足，期望空候选报告，而不是模型推荐别的股票。
4. 报告目录改为不可写，期望中间结果仍在。
5. 不配置模型或断网，期望 Python 命令仍能出报告骨架。

另外：录制 2–3 分钟备用视频；冻结依赖版本；把启动命令写进 README。演示 Profile 的 patch 在这天之后不再改。

### Day 6 · 10 月 26 日 · 演示

运行周日验证过的版本。不升级，不加功能，不换数据日期。

---

## 13. 测试与验收

### 13.1 自动化

| 测试 | 断言 |
|---|---|
| `test_indicators.py` | 手写 60 根 K 线，MA 和 20 日收益率与手工值一致 |
| `test_screener.py` | 多头、动量、量比边界各一只，原因码稳定 |
| `test_risk.py` | 行业 3/5 触发集中警告；缺价格触发 `block` |
| `test_report.py` | Markdown 含 `data_date`、规则名、免责声明；空候选可渲染 |
| `test_cli_contract.py` | stdout 是一个 JSON 对象，含 `ok`、`tool`、`error` |

测试命令：

```sh
python -m pytest tests -q
```

没有网络的测试不许跳过主路径。AKShare 连通性单独放 `tests/manual/`，不进默认套件。

### 13.2 演示验收清单

- [ ] `dsh --version` 仍是冻结版本
- [ ] `trading-research` 在仓库根目录启动
- [ ] 固定提示词触发 Skill
- [ ] 至少三次工具调用出现在会话中
- [ ] 报告表格数字与 fixture 一致
- [ ] 报告写明非实时、非投资建议
- [ ] 备用 fixture 命令可在 2 分钟内出报告
- [ ] 备用视频可离线播放

---

## 14. 星期一演示脚本

总长 12–15 分钟。演示数据日期以 fixture `manifest.json` 为准，讲者不要说“今天的行情”，除非现场 live 模式在周日已经成功，并且开场明确说了数据截止到哪一个收盘。

| 时间 | 画面 | 讲什么 |
|---|---|---|
| 1 分钟 | 标题 | 研究员工作是一条流程。这次用 DSH 把流程定制进一个可启动的 Profile，而不是做一个会下单的机器人 |
| 2 分钟 | 架构图 | Profile 装载能力，Plugin 暴露工具，Python 计算，模型解释。点明没有 `workflow.yaml` |
| 2 分钟 | `dump-config` 或设置页 | 展示 `trading-research` 比默认 `web` 多出来的插件和 Skill |
| 2 分钟 | 输入固定提示词 | Agent 开始调用 `get_market_snapshot`，而不是直接回答市场涨跌 |
| 3 分钟 | 选股工具结果 | 打开规则表：多头排列、动量区间、量比。强调阈值在代码里，结果可重复 |
| 3 分钟 | 个股与风险 | 模型段落旁边放 JSON。若模型文本和表不一致，以表为准，这本身就是设计 |
| 2 分钟 | 报告文件 | 数据日期、来源、缺失项、空着的估值字段、免责声明 |
| 1–2 分钟 | 路线图 | 回测、组合层面的风险聚合、模拟跟踪。不做自动下单 |

备用句，接口失败时使用：

> 实时接口没有返回可验证的数据。按照设计，系统不会补造行情。下面改用已经标注日期的历史样本，走同一条工具链。

不要在失败后口头补充“上证指数大概是……”。

### 14.1 建议投影页

1. 标题与成功定义
2. 研究员一天的六步，对照系统六步
3. 职责边界：Python / DSH / 模型 / 人
4. 本机 DSH 四层：Profile、Bundle、Plugin、Skill
5. 为什么不用原生 workflow 脚本做量化
6. 工具清单与 JSON 信封
7. 规则 `trend_volume_v1`
8. 失败时不编造
9. 现场运行
10. 报告解剖
11. 验收与没做什么
12. 后续：回测、风险聚合、模拟跟踪

---

## 15. 后续路线

演示之后才考虑，不提前写进 Profile：

1. 把本地 patch 收成可安装 bundle，便于换机器复现。
2. 独立的板块涨跌数据源，验证后再把报告第二节改回“强势板块”。
3. 规则回测与成本假设。
4. 组合层风险：行业权重、相关性，而不是单票警告的简单堆叠。
5. 模拟跟踪：只记录“若按规则观察，之后发生了什么”，仍然不下单。

任何一步开始前，都不新增交易执行工具。

---

## 16. 实施时的核对命令

```sh
node --version
python3 --version
git --version
dsh --version
dsh --help
dsh --profile web --help
dsh --profile trading-research --dump-config
dsh --profile trading-research --dump-config-schema
```

`--dump-config-schema` 需要 `--profile`。检查不受信任的插件前再看 schema dump，本项目插件是本地源码，可以检查。

Python 验收：

```sh
python -m trader.cli daily --universe demo --data-mode fixture --json
python -m pytest tests -q
```

---

## 17. 设计决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| 工作流载体 | Skill + `AGENTS.md` + 类型化工具 | 本机 DSH 没有会自动执行的工作流文件 |
| 原生 `workflow` 工具 | 不用于量化主路径 | 它执行模型编写的临时脚本，无持久化、无检查点 |
| 插件数量 | 一个插件，多个工具 | 演示周减少安装失败点 |
| Bundle 拆分 | 推迟 | 三个名字先映射到模块边界 |
| 演示 Profile | 从 `web` 复制 | 要 UI，且不破坏日常 `web` |
| 数据默认 | fixture | 现场网络不可控；live 是加分项 |
| 宇宙规模 | 100–180 | 全市场筛选会超时 |
| 指标位置 | Python 内部函数 | 防止模型拼错日期 |
| 报告数字 | Python 渲染 | 模型只摘要，不回写表格 |
| 交易动作 | 不存在该工具 | 研究平台不应预留下单入口 |
| 空候选 | 成功结果 | 强迫推荐会破坏可信度 |

---

## 18. 文档与代码的分工

| 文件 | 是否会被 DSH 自动执行 |
|---|---|
| 本文 | 否，给人实现和讲演 |
| `workflows/daily-stock-research.md` | 否，流程说明 |
| `AGENTS.md` | 会，作为工作区指令进入会话 |
| `.dsh/skills/daily-stock-research/SKILL.md` | 会，按 Skill 机制在匹配任务时加载 |
| `harness/patches/trading-research.patch.yml` | 仅在被 Profile patch 或 `--patch` 引用时生效 |
| `python/trader/**` | 仅被 CLI 或插件子进程调用 |
