// run-store: the collaboration hub. This plugin owns the Python bridge and the
// shared research config (python path, data mode, timeout). It provides a
// `researchRunStore` service that every research tool plugin injects, so the
// tool plugins hold no config and never spawn Python themselves. One run_id
// flows through snapshot -> screen -> research -> risk -> report via this store.

import { Service } from "@stock-trader/dsh-plugin-shared/cordis";
import {
  readConfig,
  runMarketSnapshot,
  runReport,
  runResearch,
  runRisk,
  runScreen,
} from "@stock-trader/dsh-plugin-shared/runner";

export const name = "research-run-store";

class ResearchRunStore extends Service {
  constructor(ctx, rawConfig) {
    super(ctx, "researchRunStore");
    this.config = readConfig(rawConfig);
  }

  snapshot(args, signal) {
    return runMarketSnapshot(this.config, args, signal);
  }

  screen(args, signal) {
    return runScreen(this.config, args, signal);
  }

  research(args, signal) {
    return runResearch(this.config, args, signal);
  }

  risk(args, signal) {
    return runRisk(this.config, args, signal);
  }

  report(args, signal) {
    return runReport(this.config, args, signal);
  }
}

export function apply(ctx: {
  plugin: (service: unknown, config: unknown) => void;
}, rawConfig: {
  python?: string;
  module?: "trader.cli";
  projectRoot?: string;
  dataMode?: "fixture" | "live";
  timeoutMs?: number;
}): void {
  ctx.plugin(ResearchRunStore, rawConfig);
}
