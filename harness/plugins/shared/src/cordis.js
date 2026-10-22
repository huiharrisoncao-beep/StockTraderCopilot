// Shared bridge to the cordis Service base, loaded by absolute file URL for the
// same realpath reason as the dsh-tools bridge.

import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const dshHome = process.env.DSH_HOME || join(homedir(), ".dsh");
const cordisEntry = pathToFileURL(
  join(dshHome, "profiles/node_modules/@deepseek-ai/cordis/lib/index.js"),
).href;

const mod = await import(cordisEntry);

export const Service = mod.Service;
