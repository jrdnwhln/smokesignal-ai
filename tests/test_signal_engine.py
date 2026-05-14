from app.signal_engine import calculate_confluence_score, get_priority
from app.ai_writer import generate_alert_text
from app.intelligence import agent_state, build_operator_briefing, intelligence_status
from app.market_reader import read_market
from app.strategy_engine import strategy_status


def test_score_is_between_0_and_10():
    alert = calculate_confluence_score("NVDA")
    assert 0 <= alert["score"] <= 10


def test_high_priority_threshold():
    assert get_priority(8.0) == "HIGH PRIORITY"
    assert get_priority(9.5) == "HIGH PRIORITY"


def test_watch_threshold():
    assert get_priority(6.5) == "WATCH"
    assert get_priority(7.9) == "WATCH"


def test_no_alert_threshold():
    assert get_priority(6.4) == "NO ALERT"
    assert get_priority(0.0) == "NO ALERT"


def test_should_alert_only_for_watch_or_high_priority():
    high_alert = calculate_confluence_score("NVDA")
    quiet_alert = calculate_confluence_score("AAPL")

    assert high_alert["priority"] in {"WATCH", "HIGH PRIORITY"}
    assert high_alert["should_alert"] is True

    if quiet_alert["priority"] == "NO ALERT":
        assert quiet_alert["should_alert"] is False


def test_twin_voice_includes_disclaimer():
    alert = calculate_confluence_score("NVDA")
    text = generate_alert_text(alert, "twin")
    assert "Twin" in text
    assert "get off yo ass" in text
    assert "No excuse mode" in text
    assert "Bag discipline" in text
    assert "Not financial advice. Market alerts only." in text


def test_forex_symbol_returns_forex_asset_type():
    alert = calculate_confluence_score("EURUSD")
    assert alert["asset_type"] == "forex"
    assert 0 <= alert["score"] <= 10


def test_stock_symbol_returns_stock_asset_type():
    alert = calculate_confluence_score("NVDA")
    assert alert["asset_type"] == "stock"
    assert 0 <= alert["score"] <= 10


def test_intelligence_status_has_identity():
    status = intelligence_status()
    assert status["identity"]["name"] == "SmokeSignal AI"
    assert status["learning_type"] == "local memory and adaptive heuristics"


def test_intelligence_briefing_is_personable_and_safe():
    briefing = build_operator_briefing("twin")
    assert "briefing" in briefing
    assert "Not financial advice. Market alerts only." in briefing["briefing"]


def test_agent_state_has_autonomous_goals():
    state = agent_state()
    assert state["active"] in {True, False}
    assert "Continuously monitor selected markets." in state["goals"]


def test_alert_includes_strategy_methods():
    alert = calculate_confluence_score("NVDA")
    assert len(alert["strategies"]) >= 3
    assert any(strategy["id"] == "momentum_news_confluence" for strategy in alert["strategies"])


def test_strategy_status_has_library():
    status = strategy_status()
    assert "library" in status
    assert any(strategy["id"] == "news_catalyst_watch" for strategy in status["library"])


def test_market_reader_returns_regime_and_safe_text():
    read = read_market("twin")
    assert "regime" in read
    assert "asset_summaries" in read
    assert "Not financial advice. Market alerts only." in read["read_text"]
