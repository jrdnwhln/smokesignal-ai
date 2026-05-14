from __future__ import annotations

from typing import Any

from app.database import get_strategy_memory, init_db, record_strategy_observation


STRATEGY_LIBRARY = [
    {
        "id": "momentum_news_confluence",
        "name": "Momentum + News Confluence",
        "description": "Looks for strong price movement, elevated volume, volatility, and a live news catalyst lining up.",
        "best_for": ["stock", "crypto"],
    },
    {
        "id": "volume_breakout_confirmation",
        "name": "Volume Breakout Confirmation",
        "description": "Looks for a meaningful price push confirmed by unusual volume.",
        "best_for": ["stock", "crypto"],
    },
    {
        "id": "volatility_expansion_watch",
        "name": "Volatility Expansion Watch",
        "description": "Looks for volatility expanding enough to make a symbol worth monitoring closely.",
        "best_for": ["stock", "crypto", "forex"],
    },
    {
        "id": "news_catalyst_watch",
        "name": "News Catalyst Watch",
        "description": "Looks for source-backed headlines or summaries that may explain market attention.",
        "best_for": ["stock", "crypto", "forex"],
    },
    {
        "id": "mean_reversion_caution",
        "name": "Mean Reversion Caution",
        "description": "Flags fast moves without enough volume or news confirmation as possible chase-risk setups.",
        "best_for": ["stock", "crypto", "forex"],
    },
]


def _clamp_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _strategy_template(strategy_id: str) -> dict[str, Any]:
    for strategy in STRATEGY_LIBRARY:
        if strategy["id"] == strategy_id:
            return strategy
    raise KeyError(strategy_id)


def _build_strategy(strategy_id: str, confidence: float, fired: bool, reason: str) -> dict[str, Any]:
    strategy = _strategy_template(strategy_id)
    return {
        **strategy,
        "confidence": _clamp_confidence(confidence),
        "fired": fired,
        "reason": reason,
    }


def evaluate_strategies(alert: dict[str, Any]) -> list[dict[str, Any]]:
    """Tag an alert with strategy methods and confidence.

    These are monitoring methods, not trading instructions. The strategy layer
    teaches SmokeSignal which setups are appearing so outcome grading can be
    added later.
    """
    scores = alert["component_scores"]
    price = float(scores["price_movement"])
    volume = float(scores["volume"])
    volatility = float(scores["volatility"])
    news = float(scores["news_catalyst"])
    sentiment = float(scores["sentiment"])

    momentum_confidence = (price + volume + volatility + news + sentiment) / 10
    breakout_confidence = (price + volume) / 4
    volatility_confidence = volatility / 2
    catalyst_confidence = (news + sentiment) / 4
    reversion_confidence = price / 2 if price >= 1.5 and volume < 1.0 and news == 0 else 0.0

    return [
        _build_strategy(
            "momentum_news_confluence",
            momentum_confidence,
            momentum_confidence >= 0.7,
            "Multiple market and news signals are lining up." if momentum_confidence >= 0.7 else "Not enough full confluence yet.",
        ),
        _build_strategy(
            "volume_breakout_confirmation",
            breakout_confidence,
            price >= 1.0 and volume >= 1.0,
            "Price movement is backed by volume." if price >= 1.0 and volume >= 1.0 else "Price and volume are not both strong enough.",
        ),
        _build_strategy(
            "volatility_expansion_watch",
            volatility_confidence,
            volatility >= 1.5,
            "Volatility is expanding." if volatility >= 1.5 else "Volatility is still moderate.",
        ),
        _build_strategy(
            "news_catalyst_watch",
            catalyst_confidence,
            news > 0,
            "Live source-backed headlines may be acting as a catalyst." if news > 0 else "No clear live catalyst detected.",
        ),
        _build_strategy(
            "mean_reversion_caution",
            reversion_confidence,
            reversion_confidence >= 0.75,
            "Fast movement lacks confirmation, so chase risk is higher." if reversion_confidence >= 0.75 else "No major unconfirmed chase-risk setup.",
        ),
    ]


def learn_from_strategies(alert: dict[str, Any]) -> None:
    """Store the strategy methods seen during a scan."""
    init_db()
    for strategy in alert.get("strategies", []):
        record_strategy_observation(strategy, alert)


def strategy_status() -> dict[str, Any]:
    init_db()
    return {
        "library": STRATEGY_LIBRARY,
        "memory": get_strategy_memory(),
        "disclaimer": "Strategies are monitoring methods, not financial advice or trading instructions.",
    }
