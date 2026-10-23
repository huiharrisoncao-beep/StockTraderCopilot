# 插件架构：七个插件 + 一个共享包 + 一个 bundle

这次演示的主题是 DSH 插件。原来的单插件拆成**七个独立的 Cordis 插件包**，加一个**共享 lib 包**，用 **pnpm workspace** 统一链接，再用一个 **bundle** 作为加载层装进 Profile。目的是展示：**DSH 插件不只是“注册工具”，它还能提供服务、改写系统提示、提供技能、增加斜杠命令；而 bundle 把一组插件作为一个配置层一次装好。**

## 目录结构

```
harness/
  plugins/                      # pnpm workspace
    pnpm-workspace.yaml
    shared/                     # @stock-trader/dsh-plugin-shared（共享 lib 包）
      src/ runner.js schema.js dsh-tools.js cordis.js dsh-llm.js research-text.js
    run-store/                  # @stock-trader/dsh-plugin-run-store
    market-data/                # @stock-trader/dsh-plugin-market-data
    screening/                  # @stock-trader/dsh-plugin-screening
    research-report/            # @stock-trader/dsh-plugin-research-report
    guardrails/                 # @stock-trader/dsh-plugin-guardrails
    skill/                      # @stock-trader/dsh-plugin-skill
    command/                    # @stock-trader/dsh-plugin-command
    test/                       # 跨包集成测试
  bundle/                       # @stock-trader/dsh-trading-bundle（bundle 加载层）
    package.json                # dsh.bundle.patch -> ./cordis.patch.yml
    cordis.patch.yml            # 一次 insert 七个插件
```

每个插件是独立的 npm 包，`exports` 指向自己的 `src/index.ts`；都依赖 `@stock-trader/dsh-plugin-shared`（`file:../shared`）。在 `harness/plugins` 这个 workspace 里，`pnpm install` 仍把共享包符号链接进每个插件的 `node_modules`，所以本地改共享代码立刻生效，插件用包名 `@stock-trader/dsh-plugin-shared/...` 引用共享代码。

## 七个插件与扩展点

| 插件包 | 扩展点 | 具体工作 |
|---|---|---|
| `@stock-trader/dsh-plugin-run-store` | **服务（Service）** | 持有唯一配置（Python 路径、`dataMode`、超时）。提供 `researchRunStore`，把五步调用转成 `trader.cli` 的 `market-snapshot` / `screen` / `stock-research` / `check-risk` / `report`。不注册工具 |
| `@stock-trader/dsh-plugin-market-data` | 工具 | `ping_research` 只做健康检查，不读行情。`get_market_snapshot` 读取冻结样本，写出 `run_id`、指数、涨跌家数、`data_date` 和 warnings，schema 校验后才交给模型 |
| `@stock-trader/dsh-plugin-screening` | 工具 | `screen_stocks` 只接受已有 `run_id`，按 `trend_volume_v1` 读出候选（可限 1–10 只）。候选为空是合法结果；不另传日期，也不改规则重跑 |
| `@stock-trader/dsh-plugin-research-report` | 工具 | `get_stock_research_data` 把前 5 名展开成研究卡（估值 / 新闻 / 资金流固定为空）；`check_stock_risk` 检查规则命中，`block` 移出重点、`warn` 不是卖出；`generate_daily_report` 把这次 run 渲染成 Markdown 和 JSON |
| `@stock-trader/dsh-plugin-guardrails` | **系统提示（systemPrompt）** | 不注册工具。在系统提示插入 `stock-research:guardrails`：禁止买卖指令和目标价；数字只能引用工具 JSON；`data_date` 不是“今天”；空字段不是“暂无利空” |
| `@stock-trader/dsh-plugin-skill` | **技能（skills）** | 注册 `stock-research-pipeline`（模型和用户都可调用）。内容是七步规程：快照失败即停，同一 `run_id` 贯穿，不研究候选外的代码，摘要只复述观察条件。与磁盘上的 `daily-stock-research` 分开命名，避免被挡住 |
| `@stock-trader/dsh-plugin-command` | **斜杠命令（commands）** | `/research` 把固定提示词作为一条新的用户消息送进当前会话，`universe` 默认 `demo`。回执写明只引用工具数字、不给买卖指令 |

## 每个插件完成的业务

| 插件 | 研究员工作里的那一段 |
|---|---|
| run-store | 一次盘后研究的案卷。开案时记下数据模式和截止日；选股、个股、风险、报告都读同一份档案，避免前后数字对不上 |
| market-data | 先看市场。确认样本截止哪一天、指数收在哪里、涨跌家数如何，再决定进不进选股。健康检查不算研究 |
| screening | 按写明的规则选股，不是模型挑票。历史够、多头排列、20 日涨幅落在区间、放量但不极端。按涨幅取前 10 做候选；没有票也是结论 |
| research-report | 研究收尾三段。个股卡只摆事实（价格、均线、动量、量能、距阶段高点），不写观点、不补财务和新闻。风险只报规则命中：数据缺失就移出重点，走弱、异常波动、行业扎堆、样本过期只警示。最后落一份可复核的盘后报告 |
| guardrails | 职业边界。可以写观察条件，不能下买卖指令、目标价或仓位；没接到的数据不能说成“暂无利空”；空候选不能改规则再找一只更好看的 |
| skill | 作业手册。用户说盘后研究、每日研究或选股报告时，按固定顺序做完；某步失败就停；摘要只复述工具里的数字和观察条件 |
| command | 开工按钮。`/research` 按当天规程开始这次盘后研究，默认用演示股票池 |

## 一次盘后研究怎么走

```text
用户 /research 或“盘后研究”
        │
        ▼
     Agent                         Context
  读护栏和技能          ┌──────────────────────────────────┐
  按顺序调工具          │ guardrails   skill               │
  只解释 JSON           │ command                          │
        │               │ market-data → screening → research-report
        │               │            inject               │
        └──────────────▶│           run-store              │
                        └──────────────┬───────────────────┘
                                       ▼
                              Python · SQLite · 报告
```

command 把固定提示词送进会话。Agent 从 Context 读取 guardrails 和 skill，再依次调用三个工具插件。三个工具插件都不自己起进程，而是 inject `researchRunStore`。run-store 用同一个 `run_id` 调 Python。结果回到 Agent，Agent 只做摘要，不改数字、不下单。

## bundle 怎么加载

bundle 是一个 npm 包，`package.json` 里写 `dsh.bundle.patch` 指向一份 patch。把 bundle 名字加进 Profile 的 `dsh.profile.bundles`，它的 patch 就作为**一个独立的组合层**生效：

```jsonc
// ~/.dsh/profiles/trading-research/package.json
{
  "dependencies": {
    "@stock-trader/dsh-trading-bundle": "link:<repo>/harness/bundle"
  },
  "dsh": { "profile": { "bundles": [
    "@deepseek-ai/dsh-base",
    "@deepseek-ai/dsh-web-app",
    "@stock-trader/dsh-trading-bundle"   // 新增这一行
  ] } }
}
```

`dsh --profile trading-research --dump-config` 里会出现独立的一层：

```
# == @stock-trader/dsh-trading-bundle
- id: research-run-store
  name: '@stock-trader/dsh-plugin-run-store'
  ...（七条）
```

插件不写进 Profile 的 `package.json`。bundle 的 `dependencies` 用 `file:` 指向七个插件和共享包；Profile 只 `link:` 这一个 bundle，并把它写进 `dsh.profile.bundles`。

安装时还要放一份 [profile.pnpmfile.cjs](../harness/bundle/profile.pnpmfile.cjs) 到 Profile 目录（文件名是 `.pnpmfile.cjs`）。原因有两层：pnpm 的 `link:` 不安装被链接包自己的依赖；直接用 `file:` 又会把插件的 `.ts` 源码拷进 `node_modules`，而 Node 拒绝在 `node_modules` 里剥离类型。这份 pnpmfile 在安装时把 bundle 的依赖提升成指向仓库源码的符号链接，`package.json` 里仍然只有 bundle。Profile 的 `pnpm-workspace.yaml` 要用 `nodeLinker: isolated`；`hoisted` 会清掉插件目录里指向共享包的链接。

## 协作：服务是核心

三个工具插件都不带配置，也不自己拉起 Python。它们 `inject: ["tools", "researchRunStore"]`，在 `apply` 时拿到共享服务（在活动上下文里取一次引用，避免 execute 时落到 inactive context），调用 `store.snapshot/screen/research/risk/report`。

```
research-run-store ──provides──> researchRunStore (service)
        ▲                               │
        │ inject                        │ 一个 run_id 贯穿
   ┌────┴────┬───────────────┐          ▼
 market-data  screening  research-report
```

- **单一配置点**：改 Python 路径或把 `dataMode` 从 `fixture` 切 `live`，只改 bundle patch 里 run-store 一条 config。
- **一个 run_id 贯穿**：快照产生的 `run_id` 经同一个服务传到选股、个股、风险、报告，底层共享同一份 SQLite。

## 不是工具的插件，才体现“广度”

- `guardrails` 不注册任何工具，只往系统提示加一段护栏，塑造 Agent 行为。
- `skill` 把技能随插件发布，装插件即带流程说明。
- `command` 给 UI 加 `/research`，用 `invocation.agent.followup` 注入一条用户消息。

## 安装与验证

```sh
# 1) 链接 workspace（把共享包链进每个插件）
cd harness/plugins && pnpm install

# 2) Profile 只依赖这一个 bundle，并用 pnpmfile 提升 bundle 的依赖
cp harness/bundle/profile.pnpmfile.cjs ~/.dsh/profiles/trading-research/.pnpmfile.cjs
dsh plugin --profile trading-research install

# 3) 组合层可见七条插件
dsh --profile trading-research --dump-config | grep -A1 'dsh-trading-bundle'

# 4) 跨包集成测试（真实 Cordis Context 挂载七个插件）
node --experimental-strip-types --test harness/plugins/test/plugins.test.mjs
node --experimental-strip-types --test harness/plugins/test/runner.test.mjs
```

集成测试断言：工具插件注入共享服务并注册全部工具；一个 `run_id` 跑通快照→选股→个股→风险→报告；护栏段进入系统提示；技能进入技能表；`/research` 触发固定提示词。Profile 启动无插件加载错误。要让工具挂进会话，仍需在 Web UI 把工作区加到本仓库。
