// Integration test for the multi-plugin split. Mounts the real plugin modules on
// a real cordis Context with lightweight host-service fakes (tools, systemPrompt,
// skills, commands). Confirms the researchRunStore service provided by run-store
// is injected by the tool plugins and that one run_id flows through every stage.
// Python calls are real but local, like runner.test.mjs. No network.

import assert from "node:assert/strict";
import { homedir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const { Context, Service } = await import(
  pathToFileURL(join(dshHome, "profiles/node_modules/@deepseek-ai/cordis/lib/index.js")).href
);

const runStore = await import(new URL("../run-store/src/index.ts", import.meta.url));
const marketData = await import(new URL("../market-data/src/index.ts", import.meta.url));
const screening = await import(new URL("../screening/src/index.ts", import.meta.url));
const researchReport = await import(new URL("../research-report/src/index.ts", import.meta.url));
const guardrails = await import(new URL("../guardrails/src/index.ts", import.meta.url));
const skill = await import(new URL("../skill/src/index.ts", import.meta.url));
const command = await import(new URL("../command/src/index.ts", import.meta.url));

const STORE_CONFIG = {
  python: "/Users/harrisoncao/Workspace/StockTraderCopilot/.venv/bin/python",
  module: "trader.cli",
  projectRoot: "/Users/harrisoncao/Workspace/StockTraderCopilot",
  dataMode: "fixture",
  timeoutMs: 120000,
};

// Minimal host services the plugins inject.
class FakeTools extends Service {
  constructor(ctx) {
    super(ctx, "tools");
    this.registry = new Map();
  }
  register(tool) {
    this.registry.set(tool.name, tool);
  }
}

class FakeSystemPrompt extends Service {
  constructor(ctx) {
    super(ctx, "systemPrompt");
    this.sections = new Map();
  }
  getSectionOrder(name) {
    return name === "DEPLOYMENT_PERSONA_SUFFIX" ? 10200 : 0;
  }
  section(section) {
    this.sections.set(section.name, section);
    return () => this.sections.delete(section.name);
  }
}

class FakeSkills extends Service {
  constructor(ctx) {
    super(ctx, "skills");
    this.skills = new Map();
  }
  register(entry) {
    this.skills.set(entry.name, entry);
    return () => this.skills.delete(entry.name);
  }
}

class FakeCommands extends Service {
  constructor(ctx) {
    super(ctx, "commands");
    this.commands = new Map();
  }
  register(definition) {
    this.commands.set(definition.name, definition);
    return () => this.commands.delete(definition.name);
  }
}

function host() {
  const captured = {};
  class FakeToolsCaptured extends FakeTools {
    constructor(ctx) {
      super(ctx);
      captured.tools = this;
    }
  }
  class FakeSystemPromptCaptured extends FakeSystemPrompt {
    constructor(ctx) {
      super(ctx);
      captured.systemPrompt = this;
    }
  }
  class FakeSkillsCaptured extends FakeSkills {
    constructor(ctx) {
      super(ctx);
      captured.skills = this;
    }
  }
  class FakeCommandsCaptured extends FakeCommands {
    constructor(ctx) {
      super(ctx);
      captured.commands = this;
    }
  }
  const ctx = new Context();
  ctx.plugin({ name: "fake-tools", apply: (c) => c.plugin(FakeToolsCaptured) });
  ctx.plugin({ name: "fake-system-prompt", apply: (c) => c.plugin(FakeSystemPromptCaptured) });
  ctx.plugin({ name: "fake-skills", apply: (c) => c.plugin(FakeSkillsCaptured) });
  ctx.plugin({ name: "fake-commands", apply: (c) => c.plugin(FakeCommandsCaptured) });
  return { ctx, captured };
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 50));
}

test("tool plugins inject the shared run-store and register every tool", async () => {
  const { ctx, captured } = host();
  ctx.plugin(runStore, STORE_CONFIG);
  ctx.plugin(marketData);
  ctx.plugin(screening);
  ctx.plugin(researchReport);
  await settle();

  const names = [...captured.tools.registry.keys()].sort();
  assert.deepEqual(names, [
    "check_stock_risk",
    "generate_daily_report",
    "get_market_snapshot",
    "get_stock_research_data",
    "ping_research",
    "screen_stocks",
  ]);
});

test("one run_id flows snapshot -> screen -> research -> risk -> report through the service", async () => {
  const { ctx, captured } = host();
  ctx.plugin(runStore, STORE_CONFIG);
  ctx.plugin(marketData);
  ctx.plugin(screening);
  ctx.plugin(researchReport);
  await settle();

  const tools = captured.tools.registry;
  const snapshot = await tools.get("get_market_snapshot").execute({ universe: "demo" }, {});
  assert.equal(snapshot.ok, true);
  assert.equal(snapshot.data_date, "2026-10-21");
  assert.equal(snapshot.data.indices[0].close, 3713.03);

  const screened = await tools.get("screen_stocks").execute({ run_id: snapshot.run_id, limit: 3 }, {});
  assert.equal(screened.ok, true);
  assert.equal(screened.data.candidates[0].symbol, "300031");

  const research = await tools.get("get_stock_research_data").execute({ run_id: snapshot.run_id }, {});
  assert.equal(research.ok, true);
  assert.equal(research.data.cards[0].valuation, null);

  const risk = await tools.get("check_stock_risk").execute({ run_id: snapshot.run_id }, {});
  assert.equal(risk.ok, true);
  assert.equal(risk.data.flags.every((flag) => flag.severity === "warn" || flag.severity === "block"), true);

  const report = await tools.get("generate_daily_report").execute({ run_id: snapshot.run_id }, {});
  assert.equal(report.ok, true);
  assert.equal(report.data.cards[0].close, 26.36);
  assert.match(report.data.disclaimer, /不构成投资建议/);
});

test("guardrails plugin injects a system-prompt section without a tool", async () => {
  const { ctx, captured } = host();
  ctx.plugin(guardrails);
  await settle();
  const section = captured.systemPrompt.sections.get("stock-research:guardrails");
  assert.ok(section);
  assert.equal(section.order, 10210);
  assert.match(section.text, /不是投资顾问/);
  assert.equal(captured.tools.registry.size, 0);
});

test("skill plugin ships daily-stock-research through the skills registry", async () => {
  const { ctx, captured } = host();
  ctx.plugin(skill);
  await settle();
  const entry = captured.skills.skills.get("daily-stock-research");
  assert.ok(entry);
  assert.equal(entry.invocation.modelInvocable, true);
  assert.match(entry.content, /get_market_snapshot/);
  assert.equal(entry.source, "plugin:research-skill");
});

test("command plugin registers /research and fires the fixed prompt", async () => {
  const { ctx, captured } = host();
  ctx.plugin(command);
  await settle();
  const definition = captured.commands.commands.get("research");
  assert.ok(definition);

  const sent = [];
  const result = definition.handler({
    rawInput: "",
    agent: { followup: (message) => sent.push(message) },
  });
  assert.equal(result.kind, "success");
  assert.equal(sent.length, 1);
  const text = sent[0].content.map((part) => part.text).join("");
  assert.match(text, /盘后研究/);
  assert.match(text, /universe=demo/);
});
