# Day 5 故障演练记录

记录的是命令实际输出，不是“已测试”。样本和 Profile patch 没有被改写。

- `dsh --version`: `0.2.1-rc.2`
- Node: `v24.14.0`
- patch sha256: `0d9321f8c93e3f7a4e7a453e59ea28551f7a31b5fd63e442690ae6b14dfe7cb2`
- 研究插件配置与仓库 patch 一致。Profile 文件多了 DSH 自己写入的 `ui-settings-general.welcomeNoticeVersion`，以及不同的文件头注释。这两处不要在演示前改。
- 磁盘上的 `min_return_20d` 仍是 0.05: `True`
- 2026-10-22 上午尚未收盘。最近一个已完成交易日仍是 fixture 的 `2026-10-21`。这次没有重跑 `freeze-fixture`，避免换掉备用样本。

## 1. fixture 路径不存在

```json
{
  "exit": 2,
  "ok": false,
  "tool": "run_daily_research",
  "error": {
    "code": "DATA_SOURCE_UNAVAILABLE",
    "message": "找不到样本目录 missing-demo",
    "retryable": false
  },
  "data": null
}
```

## 2. 删掉候选 300031 最后一根收盘价

```json
{
  "exit": 0,
  "ok": true,
  "error": null,
  "300031": "DATA_INCOMPLETE",
  "300031_in_candidates": false,
  "first_candidate": "603626"
}
```

## 3. 规则临时改到不可能满足

```json
{
  "exit": 0,
  "ok": true,
  "error": null,
  "candidate_count": 0,
  "excluded_RETURN_OUT_OF_RANGE": 33,
  "report_candidates": 0,
  "disclaimer": "研究结果仅用于演示研究流程，不构成投资建议，不保证收益，不触发任何交易。",
  "markdown_has_buy": false,
  "markdown_has_sell": false,
  "disk_rule_unchanged": true
}
```

## 4. 报告目录不可写

```json
{
  "exit": 2,
  "ok": false,
  "tool": "run_daily_research",
  "error": {
    "code": "REPORT_WRITE_FAILED",
    "message": "报告写盘失败",
    "retryable": true
  },
  "run_id": "research-20261022-082009",
  "data_date": "2026-10-21",
  "data": null,
  "sqlite_counts": {
    "screen_hits": 10,
    "research_cards": 5,
    "risk_flags": 9,
    "reports": 0
  }
}
```

## 5. 不配置模型，代理指向关闭端口

```json
{
  "exit": 0,
  "seconds": 0.783,
  "ok": true,
  "error": null,
  "data_date": "2026-10-21",
  "first_symbol": "300031",
  "first_close": 26.36,
  "report": "reports/2026-10-21/research-20261022-082010.md",
  "disclaimer_in_markdown": true,
  "repeat_same_order": true
}
```
