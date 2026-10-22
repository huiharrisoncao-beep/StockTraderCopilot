// research-command: adds a /research slash command that fires the fixed research
// prompt as a new user turn. Demonstrates a plugin that extends the UI surface,
// not just the tool list.

import { createUserMessage } from "@stock-trader/dsh-plugin-shared/dsh-llm";
import { FIXED_PROMPT } from "@stock-trader/dsh-plugin-shared/research-text";

export const name = "research-command";
export const inject = ["commands"];

export function apply(ctx: {
  commands: {
    register: (definition: {
      name: string;
      description: string;
      input?: { hint: string };
      handler: (invocation: unknown) => { kind: string; text: string };
    }) => unknown;
  };
}): void {
  ctx.commands.register({
    name: "research",
    description: "按固定提示词开始 fixture 盘后研究（只引用工具 JSON，不给买卖指令）",
    input: { hint: "[demo]" },
    handler: (invocation: {
      rawInput?: string;
      agent?: { followup: (message: unknown) => void };
    }) => {
      const universe = (invocation.rawInput ?? "").trim() || "demo";
      const prompt = `${FIXED_PROMPT}\nuniverse=${universe}。`;
      invocation.agent?.followup(createUserMessage({
        content: [{ type: "text", text: prompt }],
        source: { kind: "user" },
      }));
      return {
        kind: "success",
        text: `已按固定提示词开始盘后研究（universe=${universe}）。只会引用工具返回的数字，不会给买卖指令。`,
      };
    },
  });
}
