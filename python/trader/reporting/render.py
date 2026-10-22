"""Render a report from stored JSON. The model must not rewrite these tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trader.contracts import REPORT_WRITE_FAILED, TraderError
from trader.paths import project_root, reports_dir
from trader.risk.checks import blocked_symbols, focus_symbols

DISCLAIMER = "研究结果仅用于演示研究流程，不构成投资建议，不保证收益，不触发任何交易。"


def render_markdown(context: dict[str, Any]) -> str:
    market = context["market"]
    screening = context["screening"]
    cards = context["cards"]
    flags = context["flags"]
    industries = industry_distribution(screening.get("candidates", []))
    focus = focus_symbols(cards, flags)
    blocked = blocked_symbols(cards, flags)
    lines = [
        "# A 股盘后研究报告",
        "",
        "## 一、报告信息与数据日期",
        "",
        f"- run_id: {context['run_id']}",
        f"- data_date: {context['data_date']}",
        f"- generated_at: {context['generated_at']}",
        f"- universe: {context.get('universe') or 'demo'}",
        f"- rule_set: {screening.get('rule_set', '')}",
        "- 数据日期不是“今天”。这是已经冻结的样本，除非来源另有说明。",
        "",
        "## 二、市场环境",
        "",
        "<!-- table:market:start -->",
        "| 代码 | 名称 | 收盘 | 涨跌幅 | 成交额 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in market.get("indices") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row.get("code")),
                    _cell(row.get("name")),
                    _cell(row.get("close")),
                    _cell(row.get("change_pct")),
                    _cell(row.get("amount")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "<!-- table:market:end -->",
            "",
            f"上涨 {market.get('advance_count')}，下跌 {market.get('decline_count')}，平盘 {market.get('flat_count')}。",
            f"涨跌家数范围是 `{market.get('breadth_scope')}`，不是交易所官方全市场统计。",
            str(market.get("breadth_note") or ""),
            "",
            "## 三、候选行业分布",
            "",
            "这是候选集中的行业分布，不是全市场板块涨幅排名。",
            "",
            "<!-- table:industries:start -->",
            "| 行业 | 只数 |",
            "| --- | --- |",
        ]
    )
    for row in industries:
        lines.append(f"| {_cell(row['industry'])} | {row['count']} |")
    lines.extend(
        [
            "<!-- table:industries:end -->",
            "",
            "## 四、候选股票与筛选依据",
            "",
            f"规则 `{screening.get('rule_set', '')}`。{screening.get('rules', {}).get('note', '')}",
            "",
            "<!-- table:candidates:start -->",
            "| 代码 | 名称 | 行业 | 收盘 | MA20 | MA60 | 20日收益率 | 量比 | 距60日高点 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in screening.get("candidates") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row.get("symbol")),
                    _cell(row.get("name")),
                    _cell(row.get("industry")),
                    _cell(row.get("close")),
                    _cell(row.get("ma20")),
                    _cell(row.get("ma60")),
                    _cell(row.get("return_20d")),
                    _cell(row.get("volume_ratio")),
                    _cell(row.get("distance_to_high_60d")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "<!-- table:candidates:end -->",
            "",
            "排除统计: " + _counts(screening.get("excluded_counts") or {}),
            "",
            "## 五、重点个股研究",
            "",
            "下面只复述研究卡里的数字。valuation、news、fund_flow 留空，是因为没有接入这些数据源，不能解读成暂无利空。",
            "",
            "<!-- table:research:start -->",
            "| 代码 | 名称 | 收盘 | MA20 | MA60 | 20日收益率 | 量比 | 收盘高于MA20比例 | 缺失字段 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    visible = [card for card in cards if card["symbol"] in focus]
    for card in visible:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(card.get("symbol")),
                    _cell(card.get("name")),
                    _cell(card.get("close")),
                    _cell(card.get("ma20")),
                    _cell(card.get("ma60")),
                    _cell(card.get("return_20d")),
                    _cell(card.get("volume_ratio")),
                    _cell(card.get("closes_above_ma20_ratio")),
                    _cell(",".join(card.get("missing_fields") or []) or "无"),
                ]
            )
            + " |"
        )
    lines.append("<!-- table:research:end -->")
    lines.append("")
    if not cards:
        lines.append("尚未展开个股研究。不要用筛选表以外的数字补充。")
    elif not visible:
        lines.append("研究卡都因数据不完整被移出重点研究。")
    else:
        for card in visible:
            lines.append(
                f"{card['symbol']} 收盘 {_cell(card.get('close'))}，MA20 {_cell(card.get('ma20'))}，"
                f"MA60 {_cell(card.get('ma60'))}，20日收益率 {_cell(card.get('return_20d'))}，"
                f"量比 {_cell(card.get('volume_ratio'))}，近20日收盘位于 MA20 之上的比例 "
                f"{_cell(card.get('closes_above_ma20_ratio'))}。"
            )
    if blocked:
        lines.append("因缺少价格或指标而移出重点研究: " + ",".join(blocked) + "。")
    lines.extend(
        [
            "",
            "## 六、观察条件",
            "",
            "若后续收盘不再高于 MA20，或 MA20 不再高于 MA60，则不再满足 "
            f"`{screening.get('rule_set', 'trend_volume_v1')}`。",
            "若 20 日收益率离开 0.05 到 0.40，或量比离开 1.2 到 3.0，同样不再满足该规则。",
            "这是规则失效描述，不是交易指令，也不构成委托。",
            "",
            "## 七、风险提示与失效条件",
            "",
        ]
    )
    if flags:
        lines.append("<!-- table:risk:start -->")
        lines.append("| 代码 | 级别 | 规则 | 说明 |")
        lines.append("| --- | --- | --- | --- |")
        for flag in flags:
            lines.append(
                "| "
                + " | ".join(
                    [_cell(flag["symbol"]), _cell(flag["severity"]), _cell(flag["code"]), _cell(flag["message"])]
                )
                + " |"
            )
        lines.append("<!-- table:risk:end -->")
        lines.append("")
        lines.append("warn 只进入风险段。不要把警告改写成卖出或减仓。")
    else:
        lines.append("本次没有已保存的风险命中。如果还没有调用风险检查，不要补写风险结论。")
    lines.extend(
        [
            "",
            "## 八、数据来源与质量说明",
            "",
            f"- provider: {_cell(context.get('source', {}).get('provider'))}",
            f"- dataset: {_cell(context.get('source', {}).get('dataset'))}",
            f"- adjustment: {_cell(context.get('source', {}).get('adjustment'))}",
            f"- note: {_cell(context.get('source', {}).get('note'))}",
            "- 未接入字段: valuation, news, fund_flow。",
            "",
            "## 九、下一交易日观察清单",
            "",
            "只列出仍在重点研究中的代码，供人工按同一规则复核。这不是观察清单以外的交易安排。",
            "",
        ]
    )
    if focus:
        lines.append("<!-- table:watch:start -->")
        lines.append("| 代码 | 名称 | 收盘 | 规则 |")
        lines.append("| --- | --- | --- | --- |")
        by_symbol = {card["symbol"]: card for card in cards}
        for symbol in focus:
            card = by_symbol[symbol]
            lines.append(
                f"| {_cell(symbol)} | {_cell(card.get('name'))} | {_cell(card.get('close'))} | {_cell(card.get('rule_set'))} |"
            )
        lines.append("<!-- table:watch:end -->")
    else:
        lines.append("没有可复核的重点代码。")
    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def render_document(context: dict[str, Any]) -> dict[str, Any]:
    cards = context["cards"]
    flags = context["flags"]
    return {
        "run_id": context["run_id"],
        "data_date": context["data_date"],
        "generated_at": context["generated_at"],
        "market": context["market"],
        "screening": context["screening"],
        "cards": cards,
        "flags": flags,
        "industry_distribution": industry_distribution(context["screening"].get("candidates", [])),
        "focus_symbols": focus_symbols(cards, flags),
        "blocked_symbols": blocked_symbols(cards, flags),
        "disclaimer": DISCLAIMER,
    }


def industry_distribution(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in candidates:
        industry = row.get("industry")
        label = industry.strip() if isinstance(industry, str) and industry.strip() else "未标注"
        counts[label] = counts.get(label, 0) + 1
    return [
        {"industry": name, "count": counts[name]}
        for name in sorted(counts, key=lambda item: (-counts[item], item))
    ]


def write_report(context: dict[str, Any]) -> tuple[str, str]:
    markdown = render_markdown(context)
    document = render_document(context)
    target = reports_dir() / str(context["data_date"])
    try:
        target.mkdir(parents=True, exist_ok=True)
        markdown_path = target / f"{context['run_id']}.md"
        json_path = target / f"{context['run_id']}.json"
        markdown_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise TraderError(REPORT_WRITE_FAILED, "报告写盘失败", retryable=True) from exc
    return _relative(markdown_path), _relative(json_path)


def _counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "无"
    return ", ".join(f"{key} {counts[key]}" for key in sorted(counts))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    return text.replace("|", "/").replace("\n", " ")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root()).as_posix()
    except ValueError:
        return path.as_posix()
