// Shared bridge to @deepseek-ai/dsh-tools. The plugin symlink resolves from the
// repo realpath, so a bare specifier would miss the profile node_modules. Load
// it by absolute file URL, exactly once, and reuse it from every tool plugin.

import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const toolsEntry = pathToFileURL(
  join(dshHome, "profiles/node_modules/@deepseek-ai/dsh-tools/lib/index.js"),
).href;

const mod = await import(toolsEntry);

export const defineTool = mod.defineTool;

const validateJsonSchemaValue = mod.validateJsonSchemaValue;
const valueSchemaSpecToJsonSchema = mod.valueSchemaSpecToJsonSchema;

// Validate a tool envelope against its declared output schema. A mismatch never
// throws into the agent loop; it collapses to an INTERNAL envelope instead.
export function accept(schema, tool, payload) {
  const compiled = valueSchemaSpecToJsonSchema(schema);
  const violations = validateJsonSchemaValue(compiled, payload, "value");
  if (violations.length === 0) return payload;
  return {
    ok: false,
    tool,
    run_id: null,
    data_date: null,
    generated_at: payload?.generated_at ?? new Date().toISOString(),
    source: { provider: null, dataset: null, adjustment: "qfq" },
    warnings: [],
    error: { code: "INTERNAL", message: "工具结果不符合信封", retryable: false },
    data: null,
  };
}

// A single text render for every research envelope.
export function renderEnvelope(_args, value) {
  return [{ type: "text", text: JSON.stringify(value) }];
}
