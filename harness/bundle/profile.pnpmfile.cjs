// Installed as ~/.dsh/profiles/trading-research/.pnpmfile.cjs.
//
// The profile package.json depends only on this bundle. pnpm's link: protocol
// does not install a linked package's own dependencies, and file: would copy
// the TypeScript plugin sources under node_modules, where Node refuses to
// strip types. This hook lifts the bundle's dependencies into the profile
// install as symlinks back to the repo, without writing them into package.json.

const fs = require("node:fs");
const path = require("node:path");

// Absolute on purpose: this file is copied to the profile directory, so
// __dirname would no longer be the bundle directory.
const bundleDir = "/Users/harrisoncao/Workspace/StockTraderCopilot/harness/bundle";

function readPackage(pkg) {
  if (pkg.name !== "dsh-profile-trading-research") return pkg;
  const bundle = JSON.parse(fs.readFileSync(path.join(bundleDir, "package.json"), "utf8"));
  pkg.dependencies = { ...pkg.dependencies };
  for (const [name, spec] of Object.entries(bundle.dependencies || {})) {
    if (!name.startsWith("@stock-trader/")) continue;
    const rel = String(spec).replace(/^(file:|link:)/, "");
    pkg.dependencies[name] = `link:${path.resolve(bundleDir, rel)}`;
  }
  return pkg;
}

module.exports = { hooks: { readPackage } };
