from __future__ import annotations

from collections import Counter
from typing import Any

from app.ai_writer import normalize_voice_mode
from app.market_senses import build_market_senses
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


def _all_symbols() -> list[str]:
    return DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _direction_counts(alerts: list[dict[str, Any]]) -> dict[str, int]:
    positive = 0
    negative = 0
    flat = 0
    for alert in alerts:
        change = float(alert["market_snapshot"]["price_change"])
        if change > 0.25:
            positive += 1
        elif change < -0.25:
            negative += 1
        else:
            flat += 1
    return {"positive": positive, "negative": negative, "flat": flat}


def _asset_summary(alerts: list[dict[str, Any]], asset_type: str) -> dict[str, Any]:
    group = [alert for alert in alerts if alert["asset_type"] == asset_type]
    if not group:
        return {"asset_type": asset_type, "count": 0}

    direction = _direction_counts(group)
    leaders = sorted(group, key=lambda item: item["score"], reverse=True)[:3]
    return {
        "asset_type": asset_type,
        "count": len(group),
        "average_score": _average([float(alert["score"]) for alert in group]),
        "average_price_change": _average([float(alert["market_snapshot"]["price_change"]) for alert in group]),
        "average_volatility": _average([float(alert["market_snapshot"]["volatility"]) for alert in group]),
        "direction": direction,
        "leaders": [
            {"symbol": alert["symbol"], "score": alert["score"], "priority": alert["priority"]}
            for alert in leaders
        ],
    }


def _dominant_strategy(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    fired = []
    for alert in alerts:
        for strategy in alert.get("strategies", []):
            if strategy["fired"]:
                fired.append(strategy["name"])

    if not fired:
        return {"name": "No dominant method", "count": 0}

    name, count = Counter(fired).most_common(1)[0]
    return {"name": name, "count": count}


def _source_flow(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for alert in alerts:
        for article in alert.get("articles", [])[:3]:
            source = article.get("source")
            if source:
                sources.append(source)

    return [
        {"source": source, "mentions": mentions}
        for source, mentions in Counter(sources).most_common(5)
    ]


def _classify_regime(alerts: list[dict[str, Any]]) -> dict[str, str]:
    direction = _direction_counts(alerts)
    high_scores = sum(1 for alert in alerts if alert["score"] >= 8)
    watch_scores = sum(1 for alert in alerts if alert["score"] >= 6.5)
    average_volatility = _average([float(alert["market_snapshot"]["volatility"]) for alert in alerts])
    catalyst_count = sum(1 for alert in alerts if alert["component_scores"]["news_catalyst"] > 0)

    if high_scores >= 4 and catalyst_count >= 6:
        return {"regime": "catalyst-driven tape", "confidence": "high"}
    if direction["positive"] >= direction["negative"] * 2 and watch_scores >= 5:
        return {"regime": "risk-on momentum", "confidence": "medium"}
    if direction["negative"] >= direction["positive"] * 2 and watch_scores >= 4:
        return {"regime": "risk-off pressure", "confidence": "medium"}
    if average_volatility >= 1.8:
        return {"regime": "volatility expansion", "confidence": "medium"}
    if direction["flat"] >= max(direction["positive"], direction["negative"]):
        return {"regime": "chop / wait-for-confirmation", "confidence": "medium"}
    return {"regime": "mixed tape", "confidence": "low"}


def _build_read_text(read: dict[str, Any], voice_mode: str) -> str:
    voice = normalize_voice_mode(voice_mode)
    leaders = ", ".join(
        f"{alert['symbol']} {alert['score']}/10"
        for alert in read["leaders"][:4]
    )
    regime = read["regime"]["regime"]
    method = read["dominant_strategy"]["name"]

    if voice == "atl_homie":
        return (
            f"Twin, get off yo ass, no excuse mode. Tape read say {regime}. Names talkin heavy: {leaders}. "
            f"Method makin the most noise: {method}. "
            "Stay on the grind, read the smoke, keep ya discipline ugly strong. Not financial advice. Market alerts only."
        )

    return (
        f"Market read: {regime}. Leading symbols by confluence: {leaders}. "
        f"Dominant observed method: {method}. "
        "This is market monitoring, not financial advice. Market alerts only."
    )


def read_market(voice_mode: str = "normal_clanka") -> dict[str, Any]:
    """Scan the full watchlist and synthesize a market tape read."""
    alerts = [calculate_confluence_score(symbol) for symbol in _all_symbols()]
    leaders = sorted(alerts, key=lambda item: item["score"], reverse=True)
    regime = _classify_regime(alerts)
    read = {
        "regime": regime,
        "direction": _direction_counts(alerts),
        "asset_summaries": {
            "stock": _asset_summary(alerts, "stock"),
            "crypto": _asset_summary(alerts, "crypto"),
            "forex": _asset_summary(alerts, "forex"),
        },
        "leaders": [
            {
                "symbol": alert["symbol"],
                "asset_type": alert["asset_type"],
                "score": alert["score"],
                "priority": alert["priority"],
                "reason": alert["reason"],
            }
            for alert in leaders[:6]
        ],
        "dominant_strategy": _dominant_strategy(alerts),
        "source_flow": _source_flow(alerts),
        "market_senses": build_market_senses(voice_mode),
        "disclaimer": "Not financial advice. Market alerts only.",
    }
    read["read_text"] = _build_read_text(read, voice_mode)
    return read
