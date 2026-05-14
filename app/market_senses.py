from __future__ import annotations

from collections import Counter
from typing import Any

from app.ai_writer import normalize_voice_mode
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


DISCLAIMER = "Not financial advice. Market alerts only."


def _all_symbols() -> list[str]:
    return DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 1)


def _change(alert: dict[str, Any]) -> float:
    return float(alert.get("market_snapshot", {}).get("price_change", 0.0))


def _volume(alert: dict[str, Any]) -> float:
    return float(alert.get("market_snapshot", {}).get("volume_change", 1.0))


def _volatility(alert: dict[str, Any]) -> float:
    return float(alert.get("market_snapshot", {}).get("volatility", 0.0))


def _asset(alerts: list[dict[str, Any]], asset_type: str) -> list[dict[str, Any]]:
    return [alert for alert in alerts if alert.get("asset_type") == asset_type]


def _breadth(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [alert for alert in alerts if _change(alert) > 0.25]
    negative = [alert for alert in alerts if _change(alert) < -0.25]
    flat = len(alerts) - len(positive) - len(negative)
    count = max(len(alerts), 1)
    return {
        "positive": len(positive),
        "negative": len(negative),
        "flat": flat,
        "positive_percent": round((len(positive) / count) * 100, 1),
        "negative_percent": round((len(negative) / count) * 100, 1),
    }


def _usd_stress_score(forex_alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate dollar pressure from major pairs using free reference data.

    EURUSD, GBPUSD, and AUDUSD moving down usually means USD is strengthening.
    USDJPY, USDCHF, and USDCAD moving up usually means USD is strengthening.
    This is a crude regime sensor, not a professional FX model.
    """
    usd_strength_points = 0
    pairs_seen = []
    for alert in forex_alerts:
        symbol = alert["symbol"]
        change = _change(alert)
        if symbol in {"EURUSD", "GBPUSD", "AUDUSD"}:
            usd_strength_points += -change
            pairs_seen.append({"symbol": symbol, "usd_pressure": round(-change, 2)})
        elif symbol in {"USDJPY", "USDCHF", "USDCAD"}:
            usd_strength_points += change
            pairs_seen.append({"symbol": symbol, "usd_pressure": round(change, 2)})

    score = _clamp((usd_strength_points / max(len(pairs_seen), 1)) * 40 + 50)
    if score >= 65:
        label = "dollar strength / risk pressure"
    elif score <= 35:
        label = "dollar softening / risk support"
    else:
        label = "neutral dollar pressure"
    return {"score": score, "label": label, "pairs": pairs_seen}


def _news_theme_heat(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    themes = {
        "earnings": {"earnings", "revenue", "guidance", "profit", "quarter"},
        "ai": {"ai", "artificial intelligence", "chip", "datacenter", "semiconductor"},
        "macro": {"fed", "inflation", "rates", "jobs", "treasury", "dollar"},
        "crypto": {"bitcoin", "ethereum", "crypto", "etf", "exchange", "token"},
        "regulation": {"sec", "lawsuit", "probe", "ban", "approval", "regulator"},
        "crash_language": {"crash", "selloff", "plunge", "warning", "fear", "liquidation"},
    }
    counts: Counter[str] = Counter()
    for alert in alerts:
        article_text = " ".join(
            f"{article.get('title', '')} {article.get('summary', '')}"
            for article in alert.get("articles", [])[:5]
        ).lower()
        headline_text = " ".join(alert.get("headlines", [])).lower()
        combined = f"{article_text} {headline_text}"
        for theme, keywords in themes.items():
            if any(keyword in combined for keyword in keywords):
                counts[theme] += 1

    return [{"theme": theme, "mentions": mentions} for theme, mentions in counts.most_common()]


def _leadership(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_alerts = sorted(alerts, key=lambda item: float(item["score"]), reverse=True)
    top = sorted_alerts[:5]
    top_score_share = round(sum(float(item["score"]) for item in top) / max(sum(float(item["score"]) for item in alerts), 1), 2)
    top_assets = Counter(item["asset_type"] for item in top)
    if top_score_share >= 0.48:
        label = "concentrated leadership"
    elif len(top_assets) >= 3:
        label = "broad cross-market leadership"
    else:
        label = "moderate leadership"
    return {
        "label": label,
        "top_score_share": top_score_share,
        "top_symbols": [{"symbol": item["symbol"], "asset_type": item["asset_type"], "score": item["score"]} for item in top],
        "asset_mix": dict(top_assets),
    }


def _cross_market_confirmation(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    stocks = _asset(alerts, "stock")
    crypto = _asset(alerts, "crypto")
    forex = _asset(alerts, "forex")
    stock_change = _average([_change(alert) for alert in stocks])
    crypto_change = _average([_change(alert) for alert in crypto])
    forex_vol = _average([_volatility(alert) for alert in forex])
    usd_stress = _usd_stress_score(forex)

    confirmations = []
    divergences = []
    if stock_change > 0.25 and crypto_change > 0.25 and usd_stress["score"] < 60:
        confirmations.append("stocks and crypto are confirming risk appetite")
    if stock_change < -0.25 and crypto_change < -0.25 and usd_stress["score"] > 55:
        confirmations.append("stocks and crypto are confirming risk pressure")
    if stock_change > 0.35 and crypto_change < -0.35:
        divergences.append("stocks are firm while crypto is rejecting risk")
    if stock_change < -0.35 and crypto_change > 0.35:
        divergences.append("crypto is firm while stocks are rejecting risk")
    if forex_vol >= 1.2:
        divergences.append("forex volatility is elevated enough to watch macro stress")

    return {
        "stock_average_change": stock_change,
        "crypto_average_change": crypto_change,
        "forex_average_volatility": forex_vol,
        "usd_stress": usd_stress,
        "confirmations": confirmations,
        "divergences": divergences,
    }


def _pressure_indexes(alerts: list[dict[str, Any]], breadth: dict[str, Any], cross_market: dict[str, Any]) -> dict[str, Any]:
    average_score = _average([float(alert["score"]) for alert in alerts])
    average_volume = _average([_volume(alert) for alert in alerts])
    average_volatility = _average([_volatility(alert) for alert in alerts])
    positive_breadth = breadth["positive_percent"]
    negative_breadth = breadth["negative_percent"]
    bullish_catalysts = sum(
        1
        for alert in alerts
        if float(alert.get("component_scores", {}).get("news_catalyst", 0.0)) > 0
        and float(alert.get("component_scores", {}).get("sentiment", 0.0)) >= 1.5
    )
    bearish_moves = sum(1 for alert in alerts if _change(alert) < -1.0 and _volume(alert) >= 1.5)

    gain_pressure = _clamp(
        positive_breadth * 0.45
        + average_score * 5
        + bullish_catalysts * 4
        + max(0, 60 - float(cross_market["usd_stress"]["score"])) * 0.25
    )
    crash_pressure = _clamp(
        negative_breadth * 0.55
        + average_volatility * 14
        + max(0, average_volume - 1.0) * 15
        + bearish_moves * 7
        + max(0, float(cross_market["usd_stress"]["score"]) - 50) * 0.35
    )
    uncertainty = _clamp(
        average_volatility * 18
        + len(cross_market["divergences"]) * 15
        + abs(positive_breadth - negative_breadth) * -0.2
        + 30
    )
    return {
        "gain_pressure": gain_pressure,
        "crash_pressure": crash_pressure,
        "uncertainty": uncertainty,
        "average_score": average_score,
        "average_volume": average_volume,
        "average_volatility": average_volatility,
    }


def _warnings(indexes: dict[str, Any], leadership: dict[str, Any], cross_market: dict[str, Any], themes: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if indexes["crash_pressure"] >= 70:
        warnings.append("Crash pressure is elevated: negative breadth, volatility, and volume are lining up.")
    if indexes["gain_pressure"] >= 70 and indexes["crash_pressure"] < 55:
        warnings.append("Upside pressure is broad enough to monitor for continuation signals.")
    if indexes["uncertainty"] >= 70:
        warnings.append("Uncertainty is high: conditions are noisy, so confirmation matters more than speed.")
    if leadership["label"] == "concentrated leadership":
        warnings.append("Leadership is concentrated: a few names are carrying the board.")
    if cross_market["divergences"]:
        warnings.extend(cross_market["divergences"][:2])
    if any(theme["theme"] == "crash_language" for theme in themes):
        warnings.append("News language includes stress words like crash, selloff, warning, or liquidation.")
    return warnings[:6]


def _phase(indexes: dict[str, Any]) -> str:
    if indexes["crash_pressure"] >= 75:
        return "danger tape"
    if indexes["gain_pressure"] >= 75 and indexes["crash_pressure"] < 55:
        return "expansion tape"
    if indexes["uncertainty"] >= 70:
        return "foggy tape"
    if indexes["gain_pressure"] > indexes["crash_pressure"] + 15:
        return "constructive tape"
    if indexes["crash_pressure"] > indexes["gain_pressure"] + 15:
        return "defensive tape"
    return "balanced tape"


def _briefing(senses: dict[str, Any], voice_mode: str) -> str:
    voice = normalize_voice_mode(voice_mode)
    phase = senses["phase"]
    gain = senses["indexes"]["gain_pressure"]
    crash = senses["indexes"]["crash_pressure"]
    uncertainty = senses["indexes"]["uncertainty"]
    top_warning = senses["warnings"][0] if senses["warnings"] else "No extreme cross-market warning yet."

    if voice == "atl_homie":
        return (
            f"Twin, market senses say {phase}. Gain pressure {gain}/100, crash pressure {crash}/100, "
            f"uncertainty {uncertainty}/100. {top_warning} Read the whole board, not one candle. "
            f"{DISCLAIMER}"
        )

    return (
        f"Market senses: {phase}. Gain pressure {gain}/100, crash pressure {crash}/100, "
        f"uncertainty {uncertainty}/100. {top_warning} {DISCLAIMER}"
    )


def build_market_senses(voice_mode: str = "normal_clanka") -> dict[str, Any]:
    """Build alternative cross-market signals for gain/crash monitoring."""
    alerts = [calculate_confluence_score(symbol) for symbol in _all_symbols()]
    breadth = _breadth(alerts)
    cross_market = _cross_market_confirmation(alerts)
    leadership = _leadership(alerts)
    themes = _news_theme_heat(alerts)
    indexes = _pressure_indexes(alerts, breadth, cross_market)
    senses = {
        "phase": _phase(indexes),
        "indexes": indexes,
        "breadth": breadth,
        "leadership": leadership,
        "cross_market": cross_market,
        "news_theme_heat": themes,
        "warnings": _warnings(indexes, leadership, cross_market, themes),
        "alternative_signals": [
            "market breadth",
            "cross-asset confirmation",
            "dollar stress",
            "leadership concentration",
            "volatility plus volume expansion",
            "news theme clustering",
            "risk appetite divergence",
        ],
        "disclaimer": DISCLAIMER,
    }
    senses["briefing"] = _briefing(senses, voice_mode)
    return senses
