// market-data: market tools. Injects the shared researchRunStore service and
// the tools registry. Holds no config and never spawns Python directly.

import { accept, defineTool, renderEnvelope } from "@stock-trader/dsh-plugin-shared/dsh-tools";
import { marketSnapshotSchema } from "@stock-trader/dsh-plugin-shared/schema";

export const name = "market-data";
export const inject = ["tools", "researchRunStore"];

export function apply(ctx: {
  tools: { register: (tool: unknown) => void };
  researchRunStore: {
    snapshot: (args: unknown, signal?: AbortSignal) => Promise<unknown>;
  };
}): void {
  const store = ctx.researchRunStore;
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
      render: (_args: { note?: string }, value: { ok: true; tool: string; note: string }) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    execute(args: { note?: string }) {
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
      render: renderEnvelope,
    },
    async execute(args: { universe: "demo" | "csi300"; as_of?: string }, exec: { signal?: AbortSignal }) {
      const payload = await store.snapshot(args, exec?.signal);
      return accept(marketSnapshotSchema, "get_market_snapshot", payload);
    },
  }));
}
