// research-guardrails: shapes the agent, not the tool list. It injects a durable
// system-prompt section with the compliance rails (not advice, only cite tool
// JSON, data_date is not "today"). Demonstrates a plugin that changes behavior
// without registering any tool.

import { GUARDRAILS } from "@stock-trader/dsh-plugin-shared/research-text";

export const name = "research-guardrails";
export const inject = ["systemPrompt"];

const SECTION = "stock-research:guardrails";

export function apply(ctx: {
  systemPrompt: {
    section: (section: { name: string; order: number; text: string }) => unknown;
    getSectionOrder: (name: string) => number;
  };
}): void {
  // Register during apply, like the tool plugins. The injected systemPrompt is
  // resolved while the context is active; the section lives for the plugin's
  // lifetime.
  const systemPrompt = ctx.systemPrompt;
  systemPrompt.section({
    name: SECTION,
    order: systemPrompt.getSectionOrder("DEPLOYMENT_PERSONA_SUFFIX") + 10,
    text: GUARDRAILS,
  });
}
