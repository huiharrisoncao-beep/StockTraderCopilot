// screening: the screen_stocks tool. Injects the shared researchRunStore so the
// same run_id from get_market_snapshot flows through to screening.

import { accept, defineTool, renderEnvelope } from "@stock-trader/dsh-plugin-shared/dsh-tools";
import { screenSchema } from "@stock-trader/dsh-plugin-shared/schema";

export const name = "screening";
export const inject = ["tools", "researchRunStore"];

export function apply(ctx: {
  tools: { register: (tool: unknown) => void };
  researchRunStore: {
    screen: (args: unknown, signal?: AbortSignal) => Promise<unknown>;
  };
}): void {
  const store = ctx.researchRunStore;
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
      render: renderEnvelope,
    },
    async execute(
      args: { run_id: string; rule_set?: string; limit?: number },
      exec: { signal?: AbortSignal },
    ) {
      const payload = await store.screen(args, exec?.signal);
      return accept(screenSchema, "screen_stocks", payload);
    },
  }));
}
