import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const RUN_ID = /^research-\d{8}-\d{6}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const PYTHON_PATH = /^[\w./+-]+$/;

export function readConfig(raw) {
  const python = raw?.python ?? "";
  const projectRoot = raw?.projectRoot ?? "";
  const dataMode = raw?.dataMode;
  const timeoutMs = raw?.timeoutMs;
  if (!PYTHON_PATH.test(python) || python.includes("..")) {
    throw new Error("plugin python path is not a single executable path");
  }
  if (raw?.module !== "trader.cli") {
    throw new Error("plugin module must be trader.cli");
  }
  if (!projectRoot.startsWith("/") || projectRoot.includes("\0")) {
    throw new Error("plugin projectRoot must be an absolute path");
  }
  if (dataMode !== "fixture" && dataMode !== "live") {
    throw new Error("plugin dataMode must be fixture or live");
  }
  if (typeof timeoutMs !== "number" || timeoutMs < 1000 || timeoutMs > 120000) {
    throw new Error("plugin timeoutMs must be between 1000 and 120000");
  }
  return { python, module: "trader.cli", projectRoot, dataMode, timeoutMs };
}

export async function runMarketSnapshot(config, args, signal) {
  if (args.universe !== "demo" && args.universe !== "csi300") {
    return failure("get_market_snapshot", "INVALID_ARGUMENT", "universe 只接受 demo 或 csi300");
  }
  const command = [
    "market-snapshot",
    "--universe",
    args.universe,
    "--data-mode",
    config.dataMode,
    "--json",
  ];
  if (args.as_of !== undefined) {
    if (!ISO_DATE.test(args.as_of)) {
      return failure("get_market_snapshot", "INVALID_ARGUMENT", "as_of 必须是 YYYY-MM-DD");
    }
    command.push("--as-of", args.as_of);
  }
  return runPython(config, "get_market_snapshot", command, signal);
}

export async function runResearch(config, args, signal) {
  if (args.run_id === undefined || !RUN_ID.test(args.run_id)) {
    return failure("get_stock_research_data", "INVALID_ARGUMENT", "run_id 必须来自上一步，格式 research-YYYYMMDD-HHMMSS");
  }
  const command = ["stock-research", "--run-id", args.run_id, "--json"];
  if (args.symbols !== undefined) {
    if (!Array.isArray(args.symbols) || args.symbols.length < 1 || args.symbols.length > 5) {
      return failure("get_stock_research_data", "INVALID_ARGUMENT", "symbols 必须是 1 到 5 只本次候选");
    }
    if (args.symbols.some((symbol) => !/^\d{6}$/.test(symbol)) || new Set(args.symbols).size !== args.symbols.length) {
      return failure("get_stock_research_data", "INVALID_ARGUMENT", "symbols 必须是不重复的 6 位代码");
    }
    command.push("--symbols", args.symbols.join(","));
  }
  return runPython(config, "get_stock_research_data", command, signal);
}

export async function runRisk(config, args, signal) {
  if (args.run_id === undefined || !RUN_ID.test(args.run_id)) {
    return failure("check_stock_risk", "INVALID_ARGUMENT", "run_id 必须来自上一步，格式 research-YYYYMMDD-HHMMSS");
  }
  return runPython(config, "check_stock_risk", ["check-risk", "--run-id", args.run_id, "--json"], signal);
}

export async function runReport(config, args, signal) {
  if (args.run_id === undefined || !RUN_ID.test(args.run_id)) {
    return failure("generate_daily_report", "INVALID_ARGUMENT", "run_id 必须来自上一步，格式 research-YYYYMMDD-HHMMSS");
  }
  return runPython(config, "generate_daily_report", ["report", "--run-id", args.run_id, "--json"], signal);
}

export async function runScreen(config, args, signal) {
  if (args.run_id === undefined || !RUN_ID.test(args.run_id)) {
    return failure("screen_stocks", "INVALID_ARGUMENT", "run_id 必须来自上一步，格式 research-YYYYMMDD-HHMMSS");
  }
  if (args.rule_set !== undefined && args.rule_set !== "trend_volume_v1") {
    return failure("screen_stocks", "INVALID_ARGUMENT", "Day 3 只接受规则 trend_volume_v1");
  }
  if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 10)) {
    return failure("screen_stocks", "INVALID_ARGUMENT", "limit 必须是 1 到 10 的整数");
  }
  const payload = await runPython(config, "screen_stocks", ["screen", "--run-id", args.run_id, "--json"], signal);
  if (!payload.ok || payload.data === null || typeof payload.data !== "object") return payload;
  if (args.limit === undefined) return payload;
  const screening = payload.data;
  if (!Array.isArray(screening.candidates) || screening.candidates.length <= args.limit) return payload;
  screening.candidates = screening.candidates.slice(0, args.limit);
  screening.candidate_count = screening.candidates.length;
  payload.warnings = [...payload.warnings, "已按 limit 截断展示；本次 run 的完整候选仍在本地结果中。"];
  return payload;
}

async function runPython(config, tool, command, signal) {
  const args = ["-m", config.module, ...command];
  const child = spawn(config.python, args, {
    cwd: config.projectRoot,
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      PYTHONPATH: join(config.projectRoot, "python"),
    },
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk;
  });

  const timed = new AbortController();
  const timer = setTimeout(() => timed.abort(), config.timeoutMs);
  const onParentAbort = () => timed.abort();
  signal?.addEventListener("abort", onParentAbort, { once: true });
  timed.signal.addEventListener("abort", () => child.kill("SIGKILL"), { once: true });

  const exitCode = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", resolve);
  }).catch(() => null).finally(() => {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onParentAbort);
  });

  if (stderr.trim()) writeStderr(config.projectRoot, stderr);
  if (timed.signal.aborted) {
    return failure(tool, "TIMEOUT", "Python 超时，已丢弃不完整输出", true);
  }
  if (exitCode === null) {
    return failure(tool, "INTERNAL", "Python 启动失败");
  }
  try {
    const parsed = JSON.parse(stdout);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      return failure(tool, "INTERNAL", "Python 没有返回 JSON 对象");
    }
    return parsed;
  } catch {
    return failure(tool, "INTERNAL", "Python 输出不是一个 JSON 对象");
  }
}

function writeStderr(projectRoot, stderr) {
  try {
    const dir = join(projectRoot, "data", "logs");
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, `plugin-${Date.now()}.log`), stderr, "utf8");
  } catch {
    // Logging must not replace the tool envelope.
  }
}

function failure(tool, code, message, retryable = false) {
  return {
    ok: false,
    tool,
    run_id: null,
    data_date: null,
    generated_at: new Date().toISOString(),
    source: { provider: null, dataset: null, adjustment: "qfq" },
    warnings: [],
    error: { code, message, retryable },
    data: null,
  };
}
