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

每个插件是独立的 npm 包，`exports` 指向自己的 `src/index.ts`；都依赖 `@stock-trader/dsh-plugin-shared`（`link:../shared`）。`pnpm install` 在 `harness/plugins` 下把共享包链接进每个插件的 `node_modules`，所以插件用包名 `@stock-trader/dsh-plugin-shared/...` 引用共享代码。

## 七个插件与扩展点

| 插件包 | 扩展点 | 作用 |
|---|---|---|
| `@stock-trader/dsh-plugin-run-store` | **服务（Service）** | 提供 `researchRunStore`：持有配置（Python 路径、数据模式、超时）并封装 Python CLI。唯一带 config 的插件 |
| `@stock-trader/dsh-plugin-market-data` | 工具 | `ping_research`、`get_market_snapshot` |
| `@stock-trader/dsh-plugin-screening` | 工具 | `screen_stocks` |
| `@stock-trader/dsh-plugin-research-report` | 工具 | `get_stock_research_data`、`check_stock_risk`、`generate_daily_report` |
| `@stock-trader/dsh-plugin-guardrails` | **系统提示（systemPrompt）** | 注入合规护栏段：不给买卖指令、只引用工具 JSON、`data_date` 不是“今天” |
| `@stock-trader/dsh-plugin-skill` | **技能（skills）** | 从插件内注册 `stock-research-pipeline` 技能（与文件系统的 `daily-stock-research` 分开命名，避免被项目技能遮住） |
| `@stock-trader/dsh-plugin-command` | **斜杠命令（commands）** | `/research` 一键按固定提示词发起研究 |

## bundle 怎么加载

bundle 是一个 npm 包，`package.json` 里写 `dsh.bundle.patch` 指向一份 patch。把 bundle 名字加进 Profile 的 `dsh.profile.bundles`，它的 patch 就作为**一个独立的组合层**生效：

```jsonc
// ~/.dsh/profiles/trading-research/package.json
{
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

> pnpm 的 `link:` 只建符号链接、不安装被链接包自己的依赖。所以 Profile 的 `dependencies` 同时 `link:` 了 bundle 和七个插件包，保证 patch 里的插件名在 Profile 中可解析；共享包则由 `harness/plugins` 的 workspace 安装解析。

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

# 2) Profile 里加 bundle（已写好 package.json 的 bundles 与 link: 依赖）
dsh plugin --profile trading-research install

# 3) 组合层可见七条插件
dsh --profile trading-research --dump-config | grep -A1 'dsh-trading-bundle'

# 4) 跨包集成测试（真实 Cordis Context 挂载七个插件）
node --experimental-strip-types --test harness/plugins/test/plugins.test.mjs
node --experimental-strip-types --test harness/plugins/test/runner.test.mjs
```

集成测试断言：工具插件注入共享服务并注册全部工具；一个 `run_id` 跑通快照→选股→个股→风险→报告；护栏段进入系统提示；技能进入技能表；`/research` 触发固定提示词。Profile 启动无插件加载错误。要让工具挂进会话，仍需在 Web UI 把工作区加到本仓库。
