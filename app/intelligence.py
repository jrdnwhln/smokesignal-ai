import json
import time
from threading import Thread
from typing import Any

from app.ai_writer import normalize_voice_mode
from app.database import (
    get_agent_state_values,
    get_alerts,
    get_intelligence_events,
    get_source_memory,
    get_strategy_memory,
    init_db,
    record_source_observation,
    save_intelligence_event,
    set_agent_state_value,
)
from app.strategy_engine import learn_from_strategies


SYSTEM_PERSONALITY = {
    "name": "SmokeSignal AI",
    "role": "autonomous market monitoring intelligence",
    "boundaries": [
        "Does not place trades.",
        "Does not connect to broker accounts.",
        "Does not give buy or sell instructions.",
        "Does not promise outcomes.",
    ],
}

AUTONOMOUS_GOALS = [
    "Continuously monitor selected markets.",
    "Find alignment between market movement, volatility, volume, and source-backed news.",
    "Remember recurring signal patterns and news sources locally.",
    "Communicate clearly in the selected brand voice.",
    "Stay inside market monitoring and education boundaries.",
]

_agent_thread: Thread | None = None


def observe_alert(alert: dict[str, Any]) -> None:
    """Let the intelligence layer remember useful context from each scan.

    This is not model training. It is local operational memory: symbols that keep
    firing, sources that keep appearing, and why the system cared.
    """
    init_db()
    symbol = alert.get("symbol", "")
    articles = alert.get("articles", [])
    is_catalyst = float(alert.get("component_scores", {}).get("news_catalyst", 0.0)) > 0

    for article in articles:
        record_source_observation(article.get("source", ""), symbol, is_catalyst)

    learn_from_strategies(alert)

    if alert.get("should_alert"):
        metadata = {
            "score": alert.get("score"),
            "priority": alert.get("priority"),
            "reason": alert.get("reason"),
            "sources": [article.get("source") for article in articles[:5]],
        }
        save_intelligence_event(
            event_type="signal_detected",
            symbol=symbol,
            summary=f"{symbol} triggered {alert.get('priority')} at {alert.get('score')}/10.",
            metadata=json.dumps(metadata),
        )


def _recent_focus() -> list[dict[str, Any]]:
    alerts = get_alerts(limit=50)
    symbols: dict[str, dict[str, Any]] = {}
    for alert in alerts:
        symbol = alert["symbol"]
        existing = symbols.get(symbol)
        if not existing or float(alert["score"]) > float(existing["score"]):
            symbols[symbol] = alert

    focused = list(symbols.values())
    focused.sort(key=lambda item: float(item["score"]), reverse=True)
    return focused[:5]


def _write_json_state(key: str, value: Any) -> None:
    set_agent_state_value(key, json.dumps(value))


def _read_json_state(raw_state: dict[str, Any], key: str, fallback: Any) -> Any:
    item = raw_state.get(key)
    if not item:
        return fallback
    try:
        return json.loads(item["value"])
    except Exception:
        return fallback


def agent_state() -> dict[str, Any]:
    init_db()
    raw_state = get_agent_state_values()
    return {
        "active": _read_json_state(raw_state, "active", False),
        "cycle_count": _read_json_state(raw_state, "cycle_count", 0),
        "last_cycle_at": _read_json_state(raw_state, "last_cycle_at", None),
        "last_briefing": _read_json_state(raw_state, "last_briefing", None),
        "last_focus": _read_json_state(raw_state, "last_focus", []),
        "goals": AUTONOMOUS_GOALS,
    }


def run_autonomous_cycle(voice_mode: str = "twin") -> dict[str, Any]:
    """Run one autonomous observe-think-speak cycle."""
    init_db()
    voice = normalize_voice_mode(voice_mode)

    # Local imports avoid circular dependencies with alert processing.
    from app.alert_sender import process_alert
    from app.ai_writer import generate_alert_text
    from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score

    symbols = DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"]
    alerts = []
    for symbol in symbols:
        alert = calculate_confluence_score(symbol)
        alert_text = generate_alert_text(alert, voice)
        saved_alert = process_alert(alert, alert_text)
        alerts.append({**alert, "alert_text": alert_text, "database_id": saved_alert["id"]})

    briefing = build_operator_briefing(voice)
    current_state = agent_state()
    cycle_count = int(current_state["cycle_count"]) + 1
    focus = [
        {"symbol": alert["symbol"], "score": alert["score"], "priority": alert["priority"]}
        for alert in sorted(alerts, key=lambda item: item["score"], reverse=True)[:5]
    ]

    _write_json_state("active", True)
    _write_json_state("cycle_count", cycle_count)
    _write_json_state("last_cycle_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    _write_json_state("last_briefing", briefing["briefing"])
    _write_json_state("last_focus", focus)
    save_intelligence_event(
        event_type="autonomous_cycle",
        symbol=None,
        summary=f"Autonomous cycle {cycle_count} completed across {len(symbols)} symbols.",
        metadata=json.dumps({"focus": focus}),
    )

    return {
        "cycle_count": cycle_count,
        "symbols_scanned": len(symbols),
        "focus": focus,
        "briefing": briefing["briefing"],
    }


def _autonomous_loop(interval_minutes: int, voice_mode: str) -> None:
    while True:
        run_autonomous_cycle(voice_mode)
        time.sleep(max(1, interval_minutes) * 60)


def activate_autonomous_intelligence(interval_minutes: int = 5, voice_mode: str = "twin") -> dict[str, Any]:
    """Start the local autonomous monitoring loop once per app process."""
    global _agent_thread
    init_db()
    _write_json_state("active", True)

    if _agent_thread and _agent_thread.is_alive():
        return {"started": False, "message": "SmokeSignal autonomous intelligence is already active.", "state": agent_state()}

    _agent_thread = Thread(target=_autonomous_loop, args=(interval_minutes, voice_mode), daemon=True)
    _agent_thread.start()
    save_intelligence_event(
        event_type="agent_activated",
        symbol=None,
        summary=f"Autonomous intelligence activated on a {interval_minutes}-minute loop.",
        metadata=json.dumps({"voice_mode": voice_mode}),
    )
    return {"started": True, "message": "SmokeSignal autonomous intelligence is active.", "state": agent_state()}


def intelligence_status() -> dict[str, Any]:
    """Return what the local intelligence currently knows about its work."""
    init_db()
    focus = _recent_focus()
    source_memory = get_source_memory(limit=8)
    strategy_memory = get_strategy_memory(limit=8)
    events = get_intelligence_events(limit=8)
    return {
        "identity": SYSTEM_PERSONALITY,
        "mode": "local autonomous monitor",
        "learning_type": "local memory and adaptive heuristics",
        "agent_state": agent_state(),
        "recent_focus": focus,
        "source_memory": source_memory,
        "strategy_memory": strategy_memory,
        "recent_events": events,
        "disclaimer": "Not financial advice. Market alerts only.",
    }


def build_operator_briefing(voice_mode: str = "normal_clanka") -> dict[str, Any]:
    """Create a personable briefing from recent memory and alert history."""
    voice = normalize_voice_mode(voice_mode)
    status = intelligence_status()
    focus = status["recent_focus"]
    from app.market_senses import build_market_senses

    senses = build_market_senses(voice_mode)

    if not focus:
        text = (
            "SmokeSignal is awake, but it has not built enough local scan memory yet. "
            "Run /scan so it can start tracking market behavior. Not financial advice. Market alerts only."
        )
    else:
        leaders = ", ".join(f"{item['symbol']} {item['score']}/10" for item in focus[:3])
        top_source = status["source_memory"][0]["source"] if status["source_memory"] else "live news sources"
        top_strategy = status["strategy_memory"][0]["name"] if status["strategy_memory"] else "confluence monitoring"
        if voice == "atl_homie":
            text = (
                f"Twin, SmokeSignal up and on the grind. Get off yo ass, no excuse mode. Heat on the board: {leaders}. "
                f"Source flow keep comin from {top_source}, method makin noise: {top_strategy}. "
                f"Market senses callin it {senses['phase']} with crash pressure {senses['indexes']['crash_pressure']}/100. "
                "Bag discipline, read the smoke, keep working while everybody sleep. "
                "Not financial advice. Market alerts only."
            )
        else:
            text = (
                f"SmokeSignal AI is actively monitoring. Current focus: {leaders}. "
                f"Most active recent source: {top_source}. Most observed method: {top_strategy}. "
                f"Market senses: {senses['phase']} with crash pressure {senses['indexes']['crash_pressure']}/100. "
                "Not financial advice. Market alerts only."
            )

    return {
        "briefing": text,
        "status": status,
        "market_senses": senses,
    }
