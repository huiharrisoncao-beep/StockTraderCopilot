import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const toolsEntry = pathToFileURL(
  join(dshHome, "profiles/node_modules/@deepseek-ai/dsh-tools/lib/index.js"),
).href;

const { defineTool } = await import(toolsEntry);

export const name = "stock-research";
export const inject = ["tools"];

interface PingArgs {
  note?: string;
}

interface PingResult {
  ok: true;
  tool: "ping_research";
  note: string;
}

export function apply(ctx: { tools: { register: (tool: unknown) => void } }): void {
  ctx.tools.register(defineTool({
    name: "ping_research",
    description: "Health check for the Stock Trader Copilot research plugin. Call this when the user asks to ping the research plugin. It returns fixed JSON and does not read market data.",
    parameters: {
      note: {
        type: "string",
        description: "Optional text echoed back. Do not put secrets here.",
      },
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
      render: (_args: PingArgs, value: PingResult) => [
        { type: "text", text: JSON.stringify(value) },
      ],
    },
    execute(args: PingArgs): PingResult {
      return {
        ok: true,
        tool: "ping_research",
        note: args.note?.trim() ?? "",
      };
    },
  }));
}
