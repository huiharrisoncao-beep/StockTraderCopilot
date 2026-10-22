/** Output schemas for the Day 3 envelopes. additionalProperties is always explicit. */

const nullableString = { oneOf: [{ type: "string" }, { type: "null" }] };
const nullableNumber = { oneOf: [{ type: "number" }, { type: "null" }] };

const source = {
  type: "object",
  additionalProperties: false,
  properties: {
    provider: { ...nullableString, required: true },
    dataset: { ...nullableString, required: true },
    adjustment: { type: "string", required: true },
    note: { type: "string" },
  },
};

const errorBody = {
  oneOf: [
    { type: "null" },
    {
      type: "object",
      additionalProperties: false,
      properties: {
        code: { type: "string", required: true },
        message: { type: "string", required: true },
        retryable: { type: "boolean", required: true },
      },
    },
  ],
};

const indexRow = {
  type: "object",
  additionalProperties: false,
  properties: {
    code: { type: "string", required: true },
    name: { type: "string", required: true },
    close: { type: "number", required: true },
    change_pct: { ...nullableNumber, required: true },
    amount: { ...nullableNumber, required: true },
  },
};

const market = {
  type: "object",
  additionalProperties: false,
  properties: {
    data_date: { type: "string", required: true },
    indices: { type: "array", required: true, items: indexRow },
    advance_count: { type: "integer", required: true },
    decline_count: { type: "integer", required: true },
    flat_count: { type: "integer", required: true },
    breadth_scope: { type: "string", required: true },
    spot_scope: { type: "string" },
    breadth_note: { type: "string", required: true },
  },
};

const candidate = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: { type: "string", required: true },
    name: { ...nullableString, required: true },
    industry: { ...nullableString, required: true },
    close: { type: "number", required: true },
    ma20: { type: "number", required: true },
    ma60: { type: "number", required: true },
    return_20d: { type: "number", required: true },
    volume_ratio: { type: "number", required: true },
    high_60d: { ...nullableNumber, required: true },
    distance_to_high_60d: { ...nullableNumber, required: true },
  },
};

const screening = {
  type: "object",
  additionalProperties: false,
  properties: {
    rule_set: { type: "string", required: true },
    rules: {
      type: "object",
      additionalProperties: false,
      required: true,
      properties: {
        name: { type: "string", required: true },
        min_history: { type: "integer", required: true },
        min_return_20d: { type: "number", required: true },
        max_return_20d: { type: "number", required: true },
        min_volume_ratio: { type: "number", required: true },
        max_volume_ratio: { type: "number", required: true },
        candidate_limit: { type: "integer", required: true },
        note: { type: "string", required: true },
      },
    },
    candidate_count: { type: "integer", required: true },
    eligible_count: { type: "integer", required: true },
    excluded_counts: {
      type: "object",
      additionalProperties: true,
      required: true,
    },
    exclusions: {
      type: "array",
      required: true,
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          symbol: { type: "string", required: true },
          reason: { type: "string", required: true },
        },
      },
    },
    candidates: { type: "array", required: true, items: candidate },
    universe_size: { type: "integer", required: true },
  },
};

function envelope(data) {
  return {
    type: "object",
    additionalProperties: false,
    properties: {
      ok: { type: "boolean", required: true },
      tool: { type: "string", required: true },
      run_id: { ...nullableString, required: true },
      data_date: { ...nullableString, required: true },
      generated_at: { type: "string", required: true },
      source: { ...source, required: true },
      warnings: { type: "array", required: true, items: { type: "string" } },
      error: { ...errorBody, required: true },
      data: { ...data, required: true },
    },
  };
}

const researchCard = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: { type: "string", required: true },
    name: { ...nullableString, required: true },
    industry: { ...nullableString, required: true },
    data_date: { type: "string", required: true },
    close: { ...nullableNumber, required: true },
    ma20: { ...nullableNumber, required: true },
    ma60: { ...nullableNumber, required: true },
    return_20d: { ...nullableNumber, required: true },
    volume_ratio: { ...nullableNumber, required: true },
    distance_to_high_60d: { ...nullableNumber, required: true },
    rule_set: { type: "string", required: true },
    closes_above_ma20_ratio: { ...nullableNumber, required: true },
    missing_fields: { type: "array", required: true, items: { type: "string" } },
    unavailable_fields: { type: "array", required: true, items: { type: "string" } },
    valuation: { type: "null", required: true },
    news: { type: "null", required: true },
    fund_flow: { type: "null", required: true },
  },
};

const riskFlag = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: { type: "string", required: true },
    code: { type: "string", required: true },
    severity: { type: "string", required: true, enum: ["block", "warn"] },
    message: { type: "string", required: true },
  },
};

const industryCount = {
  type: "object",
  additionalProperties: false,
  properties: {
    industry: { type: "string", required: true },
    count: { type: "integer", required: true },
  },
};

const researchData = {
  type: "object",
  additionalProperties: false,
  properties: {
    rule_set: { type: "string", required: true },
    cards: { type: "array", required: true, items: researchCard },
    symbols: { type: "array", required: true, items: { type: "string" } },
  },
};

const riskData = {
  type: "object",
  additionalProperties: false,
  properties: {
    flags: { type: "array", required: true, items: riskFlag },
    blocked_symbols: { type: "array", required: true, items: { type: "string" } },
    focus_symbols: { type: "array", required: true, items: { type: "string" } },
  },
};

const reportData = {
  type: "object",
  additionalProperties: false,
  properties: {
    markdown_path: { type: "string", required: true },
    json_path: { type: "string", required: true },
    disclaimer: { type: "string", required: true },
    market: { ...market, required: true },
    screening: { ...screening, required: true },
    cards: { type: "array", required: true, items: researchCard },
    flags: { type: "array", required: true, items: riskFlag },
    industry_distribution: { type: "array", required: true, items: industryCount },
    focus_symbols: { type: "array", required: true, items: { type: "string" } },
    blocked_symbols: { type: "array", required: true, items: { type: "string" } },
  },
};

export const marketSnapshotSchema = envelope({ oneOf: [market, { type: "null" }] });
export const screenSchema = envelope({ oneOf: [screening, { type: "null" }] });
export const researchSchema = envelope({ oneOf: [researchData, { type: "null" }] });
export const riskSchema = envelope({ oneOf: [riskData, { type: "null" }] });
export const reportSchema = envelope({ oneOf: [reportData, { type: "null" }] });
