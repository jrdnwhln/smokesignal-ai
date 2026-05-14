from app.market_data import get_market_snapshot
from app.news_scanner import detect_news_catalyst, get_recent_articles, get_recent_headlines, score_news_sentiment
from app.strategy_engine import evaluate_strategies


DEFAULT_WATCHLIST = {
    "stocks": ["SPY", "QQQ", "NVDA", "TSLA", "AMD", "AAPL", "META"],
    "crypto": ["BTC", "ETH", "SOL", "XRP"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"],
}


def get_asset_type(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol in DEFAULT_WATCHLIST["crypto"]:
        return "crypto"
    if symbol in DEFAULT_WATCHLIST["forex"]:
        return "forex"
    return "stock"


def score_price_movement(price_change: float) -> float:
    movement = abs(price_change)
    if movement >= 2.5:
        return 2.0
    if movement >= 1.5:
        return 1.5
    if movement >= 0.75:
        return 1.0
    if movement >= 0.25:
        return 0.5
    return 0.0


def score_volume(volume_change: float) -> float:
    if volume_change >= 3.0:
        return 2.0
    if volume_change >= 2.0:
        return 1.5
    if volume_change >= 1.3:
        return 1.0
    if volume_change >= 1.1:
        return 0.5
    return 0.0


def score_volatility(volatility: float) -> float:
    if volatility >= 2.5:
        return 2.0
    if volatility >= 1.8:
        return 1.5
    if volatility >= 1.2:
        return 1.0
    if volatility >= 0.8:
        return 0.5
    return 0.0


def get_priority(score: float) -> str:
    if score >= 8.0:
        return "HIGH PRIORITY"
    if score >= 6.5:
        return "WATCH"
    return "NO ALERT"


def build_reason(symbol: str, snapshot: dict, has_catalyst: bool, sentiment_score: float) -> str:
    parts = []
    if score_price_movement(float(snapshot["price_change"])) >= 1.5:
        parts.append("elevated price movement")
    if score_volume(float(snapshot["volume_change"])) >= 1.5:
        parts.append("unusual volume")
    if score_volatility(float(snapshot["volatility"])) >= 1.5:
        parts.append("high volatility")
    if has_catalyst:
        catalyst_tone = "bullish" if sentiment_score >= 1.5 else "bearish or mixed"
        parts.append(f"a {catalyst_tone} news catalyst")

    if not parts:
        return f"{symbol} does not have enough aligned market and news signals yet."

    return f"{symbol} has " + ", ".join(parts) + "."


def calculate_confluence_score(symbol: str) -> dict:
    """Calculate a 0-10 alert score from price, volume, volatility, news, and sentiment."""
    symbol = symbol.upper()
    snapshot = get_market_snapshot(symbol)
    articles = get_recent_articles(symbol)
    headlines = get_recent_headlines(symbol)
    has_catalyst = detect_news_catalyst(symbol)

    price_score = score_price_movement(float(snapshot["price_change"]))
    volume_score = score_volume(float(snapshot["volume_change"]))
    volatility_score = score_volatility(float(snapshot["volatility"]))
    catalyst_score = 2.0 if has_catalyst else 0.0
    sentiment_score = score_news_sentiment(headlines)

    total_score = round(
        price_score + volume_score + volatility_score + catalyst_score + sentiment_score,
        1,
    )
    total_score = max(0.0, min(10.0, total_score))
    priority = get_priority(total_score)

    alert = {
        "symbol": symbol,
        "asset_type": get_asset_type(symbol),
        "score": total_score,
        "priority": priority,
        "reason": build_reason(symbol, snapshot, has_catalyst, sentiment_score),
        "should_alert": priority in {"WATCH", "HIGH PRIORITY"},
        "market_snapshot": snapshot,
        "headlines": headlines,
        "articles": articles,
        "component_scores": {
            "price_movement": price_score,
            "volume": volume_score,
            "volatility": volatility_score,
            "news_catalyst": catalyst_score,
            "sentiment": sentiment_score,
        },
    }
    alert["strategies"] = evaluate_strategies(alert)
    return alert
