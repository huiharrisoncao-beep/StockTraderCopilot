// Shared bridge to @deepseek-ai/dsh-llm for createUserMessage, loaded by
// absolute file URL for the same realpath reason as the other bridges.

import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const llmEntry = pathToFileURL(
  join(dshHome, "profiles/node_modules/@deepseek-ai/dsh-llm/lib/index.js"),
).href;

const mod = await import(llmEntry);

export const createUserMessage = mod.createUserMessage;
