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

Python 包只是骨架。Day 2 再安装依赖。现在可以这样确认入口：

```sh
PYTHONPATH=python python3 -m trader.cli
```

它会以非零状态退出，并说明 CLI 尚未实现。
