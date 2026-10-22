import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { readConfig, runMarketSnapshot, runReport, runResearch, runRisk, runScreen } from "./runner.js";
import { marketSnapshotSchema, reportSchema, researchSchema, riskSchema, screenSchema } from "./schema.js";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const toolsEntry = pathToFileURL(
  join(dshHome, "profiles/node_modules/@deepseek-ai/dsh-tools/lib/index.js"),
).href;

const { defineTool, validateJsonSchemaValue, valueSchemaSpecToJsonSchema } = await import(toolsEntry);

export const name = "stock-research";
export const inject = ["tools"];

interface ToolHost {
  tools: { register: (tool: unknown) => void };
}

interface PingArgs {
  note?: string;
}

export function apply(ctx: ToolHost, rawConfig: {
  python?: string;
  module?: "trader.cli";
  projectRoot?: string;
  dataMode?: "fixture" | "live";
  timeoutMs?: number;
}): void {
  const config = readConfig(rawConfig);
  ctx.tools.register(defineTool({
    name: "ping_research",
    description: "Health check only. Call it when the user asks to ping the research plugin. It does not read market data.",
    parameters: {
      note: { type: "string", description: "Optional text echoed back. Do not put secrets here." },
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean", required: true },
          tool: { type: "string", required: true },
          note: { type: "string", required: true },
        },
      },
      render: (_args: PingArgs, value: { ok: true; tool: string; note: string }) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    execute(args: PingArgs) {
      return { ok: true, tool: "ping_research", note: args.note?.trim() ?? "" };
    },
  }));

  ctx.tools.register(defineTool({
    name: "get_market_snapshot",
    description: "Read the frozen A-share market snapshot for one research run. Call this before screen_stocks. Copy index levels, breadth, data_date, and warnings only from the returned JSON. Do not pass file paths or switch the data mode. This is not a trade order.",
    parameters: {
      universe: {
        type: "string",
        required: true,
        enum: ["demo", "csi300"],
        description: "Stock universe. The demo uses demo. csi300 is not enabled.",
      },
      as_of: {
        type: "string",
        description: "Optional YYYY-MM-DD. Omit it to use the frozen fixture date. Never change it to search for a better result.",
      },
    },
    output: {
      schema: marketSnapshotSchema,
      render: (_args: unknown, value: Envelope) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    async execute(args: { universe: "demo" | "csi300"; as_of?: string }, exec: { signal?: AbortSignal }) {
      const payload = await runMarketSnapshot(config, args, exec?.signal);
      return accept(marketSnapshotSchema, "get_market_snapshot", payload);
    },
  }));

  ctx.tools.register(defineTool({
    name: "screen_stocks",
    description: "Read screening results for an existing run_id from get_market_snapshot. Do not pass a data_date or a file path. Empty candidates are a valid result. Do not turn the result into buy or sell orders.",
    parameters: {
      run_id: {
        type: "string",
        required: true,
        description: "run_id returned by get_market_snapshot, format research-YYYYMMDD-HHMMSS.",
      },
      rule_set: {
        type: "string",
        description: "Optional. The only accepted value is trend_volume_v1.",
      },
      limit: {
        type: "integer",
        description: "Optional display cap from 1 to 10. Omit it to use the stored top 10.",
      },
    },
    output: {
      schema: screenSchema,
      render: (_args: unknown, value: Envelope) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    async execute(
      args: { run_id: string; rule_set?: string; limit?: number },
      exec: { signal?: AbortSignal },
    ) {
      const payload = await runScreen(config, args, exec?.signal);
      return accept(screenSchema, "screen_stocks", payload);
    },
  }));

  ctx.tools.register(defineTool({
    name: "get_stock_research_data",
    description: "Expand up to 5 candidates from this run into research cards. Omit symbols to use the stored top 5. Do not pass symbols that were not candidates. valuation, news, and fund_flow are always null because those sources are not connected. Do not invent fundamentals or news. This is not a trade order.",
    parameters: {
      run_id: {
        type: "string",
        required: true,
        description: "run_id returned by get_market_snapshot.",
      },
      symbols: {
        type: "array",
        items: { type: "string" },
        description: "Optional 6-digit symbols from this run's candidates, at most 5. Omit to research the stored top 5.",
      },
    },
    output: {
      schema: researchSchema,
      render: (_args: unknown, value: Envelope) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    async execute(args: { run_id: string; symbols?: string[] }, exec: { signal?: AbortSignal }) {
      const payload = await runResearch(config, args, exec?.signal);
      return accept(researchSchema, "get_stock_research_data", payload);
    },
  }));

  ctx.tools.register(defineTool({
    name: "check_stock_risk",
    description: "Check rule hits for the current run. Call it after get_stock_research_data. block removes a card from the focus list. warn is not a sell instruction. Do not pass symbols or file paths.",
    parameters: {
      run_id: {
        type: "string",
        required: true,
        description: "run_id returned by get_market_snapshot.",
      },
    },
    output: {
      schema: riskSchema,
      render: (_args: unknown, value: Envelope) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    async execute(args: { run_id: string }, exec: { signal?: AbortSignal }) {
      const payload = await runRisk(config, args, exec?.signal);
      return accept(riskSchema, "check_stock_risk", payload);
    },
  }));

  ctx.tools.register(defineTool({
    name: "generate_daily_report",
    description: "Render the stored run to Markdown and JSON. Quote numbers only from this result. Do not rewrite table values. The disclaimer means this is not investment advice and not an order.",
    parameters: {
      run_id: {
        type: "string",
        required: true,
        description: "run_id returned by get_market_snapshot.",
      },
    },
    output: {
      schema: reportSchema,
      render: (_args: unknown, value: Envelope) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    async execute(args: { run_id: string }, exec: { signal?: AbortSignal }) {
      const payload = await runReport(config, args, exec?.signal);
      return accept(reportSchema, "generate_daily_report", payload);
    },
  }));
}

interface Envelope {
  ok: boolean;
  tool: string;
  run_id: string | null;
  data_date: string | null;
  generated_at: string;
  source: { provider: string | null; dataset: string | null; adjustment: string };
  warnings: string[];
  error: { code: string; message: string; retryable: boolean } | null;
  data: unknown;
}

function accept(schema: object, tool: string, payload: Envelope): Envelope {
  const compiled = valueSchemaSpecToJsonSchema(schema);
  const violations = validateJsonSchemaValue(compiled, payload, "value");
  if (violations.length === 0) return payload;
  return {
    ok: false,
    tool,
    run_id: null,
    data_date: null,
    generated_at: payload.generated_at,
    source: { provider: null, dataset: null, adjustment: "qfq" },
    warnings: [],
    error: { code: "INTERNAL", message: "工具结果不符合信封", retryable: false },
    data: null,
  };
}
