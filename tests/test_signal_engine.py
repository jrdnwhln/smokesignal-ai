from app.signal_engine import calculate_confluence_score, get_priority
from app.ai_writer import generate_alert_text


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


def test_atl_homie_voice_includes_disclaimer():
    alert = calculate_confluence_score("NVDA")
    text = generate_alert_text(alert, "atl_homie")
    assert "turnin up" in text
    assert "Not financial advice. Market alerts only." in text


def test_forex_symbol_returns_forex_asset_type():
    alert = calculate_confluence_score("EURUSD")
    assert alert["asset_type"] == "forex"
    assert 0 <= alert["score"] <= 10


def test_stock_symbol_returns_stock_asset_type():
    alert = calculate_confluence_score("NVDA")
    assert alert["asset_type"] == "stock"
    assert 0 <= alert["score"] <= 10
