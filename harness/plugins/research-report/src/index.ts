// research-report: the per-stock research, risk, and report tools. All three
// share the same researchRunStore service and operate on one run_id.

import { accept, defineTool, renderEnvelope } from "@stock-trader/dsh-plugin-shared/dsh-tools";
import { reportSchema, researchSchema, riskSchema } from "@stock-trader/dsh-plugin-shared/schema";

export const name = "research-report";
export const inject = ["tools", "researchRunStore"];

export function apply(ctx: {
  tools: { register: (tool: unknown) => void };
  researchRunStore: {
    research: (args: unknown, signal?: AbortSignal) => Promise<unknown>;
    risk: (args: unknown, signal?: AbortSignal) => Promise<unknown>;
    report: (args: unknown, signal?: AbortSignal) => Promise<unknown>;
  };
}): void {
  const store = ctx.researchRunStore;
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
      render: renderEnvelope,
    },
    async execute(args: { run_id: string; symbols?: string[] }, exec: { signal?: AbortSignal }) {
      const payload = await store.research(args, exec?.signal);
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
      render: renderEnvelope,
    },
    async execute(args: { run_id: string }, exec: { signal?: AbortSignal }) {
      const payload = await store.risk(args, exec?.signal);
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
      render: renderEnvelope,
    },
    async execute(args: { run_id: string }, exec: { signal?: AbortSignal }) {
      const payload = await store.report(args, exec?.signal);
      return accept(reportSchema, "generate_daily_report", payload);
    },
  }));
}
