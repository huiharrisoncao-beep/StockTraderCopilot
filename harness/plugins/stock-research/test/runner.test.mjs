import assert from "node:assert/strict";
import { test } from "node:test";

const { readConfig, runMarketSnapshot, runReport, runResearch, runRisk, runScreen } = await import(new URL("../src/runner.js", import.meta.url));

const config = readConfig({
  python: "/Users/harrisoncao/Workspace/StockTraderCopilot/.venv/bin/python",
  module: "trader.cli",
  projectRoot: "/Users/harrisoncao/Workspace/StockTraderCopilot",
  dataMode: "fixture",
  timeoutMs: 120000,
});

test("invalid screen arguments do not spawn python", async () => {
  const payload = await runScreen(config, { run_id: "not-a-run" });
  assert.equal(payload.ok, false);
  assert.equal(payload.error.code, "INVALID_ARGUMENT");
});

test("fixture snapshot and screen stay off the network and agree", async () => {
  const snapshot = await runMarketSnapshot(config, { universe: "demo" });
  assert.equal(snapshot.ok, true);
  assert.equal(snapshot.tool, "get_market_snapshot");
  assert.equal(snapshot.data_date, "2026-10-21");
  assert.equal(snapshot.data.indices[0].close, 3713.03);
  assert.equal(snapshot.source.provider, "fixture");

  const screened = await runScreen(config, { run_id: snapshot.run_id, rule_set: "trend_volume_v1", limit: 3 });
  assert.equal(screened.ok, true);
  assert.equal(screened.tool, "screen_stocks");
  assert.equal(screened.data_date, snapshot.data_date);
  assert.equal(screened.data.candidates.length, 3);
  assert.equal(screened.data.candidates[0].symbol, "300031");
  assert.equal(screened.error, null);
});

test("research, risk, and report stay on the fixture", async () => {
  const snapshot = await runMarketSnapshot(config, { universe: "demo" });
  const research = await runResearch(config, { run_id: snapshot.run_id });
  assert.equal(research.ok, true);
  assert.equal(research.data.cards[0].symbol, "300031");
  assert.equal(research.data.cards[0].valuation, null);
  assert.deepEqual(research.data.cards[0].unavailable_fields, ["valuation", "news", "fund_flow"]);

  const outside = await runResearch(config, { run_id: snapshot.run_id, symbols: ["000001"] });
  assert.equal(outside.ok, false);
  assert.equal(outside.error.code, "INVALID_ARGUMENT");

  const risk = await runRisk(config, { run_id: snapshot.run_id });
  assert.equal(risk.ok, true);
  assert.equal(risk.data.flags.every((flag) => flag.severity === "warn" || flag.severity === "block"), true);

  const report = await runReport(config, { run_id: snapshot.run_id });
  assert.equal(report.ok, true);
  assert.equal(report.data.cards[0].close, 26.36);
  assert.match(report.data.disclaimer, /不构成投资建议/);
  assert.equal(report.data.industry_distribution[0].industry, "未标注");
});

test("a different as_of is rejected by the fixture", async () => {
  const payload = await runMarketSnapshot(config, { universe: "demo", as_of: "2020-01-01" });
  assert.equal(payload.ok, false);
  assert.equal(payload.error.code, "INVALID_ARGUMENT");
  assert.equal(payload.data, null);
});
