from app.config import settings


MOCK_HEADLINES = {
    "NVDA": [
        "Nvidia shares rise as AI chip demand remains strong",
        "Analysts point to fresh data center momentum for Nvidia",
    ],
    "TSLA": [
        "Tesla slips after production concerns weigh on sentiment",
        "EV sector watches new pricing updates from Tesla",
    ],
    "SOL": [
        "Solana gains as on-chain activity jumps and exchange volume expands",
        "Crypto traders watch Solana after network upgrade announcement",
    ],
    "BTC": [
        "Bitcoin holds near recent highs as ETF flows stay in focus",
        "Macro traders watch Bitcoin ahead of Fed commentary",
    ],
}

DEFAULT_HEADLINES = [
    "Markets trade mixed as investors wait for fresh economic data",
    "Sector rotation continues while volume stays near average",
    "Analysts watch earnings calendar for the next catalyst",
]

BULLISH_WORDS = {"rise", "rises", "gain", "gains", "strong", "momentum", "jumps", "upgrade", "highs", "demand"}
BEARISH_WORDS = {"slips", "falls", "concerns", "weigh", "weak", "cuts", "miss", "lawsuit", "probe"}
CATALYST_WORDS = {"earnings", "fed", "upgrade", "production", "etf", "announcement", "demand", "flows", "economic"}


def get_recent_headlines(symbol: str) -> list[str]:
    """Return recent headlines for a symbol.

    Future trusted sources can be added here, including SEC filings, company
    press releases, earnings calendars, Fed announcements, crypto exchange
    announcements, and finance news APIs.
    """
    if settings.NEWS_API_KEY:
        # Add real news API calls and source filtering here later.
        pass
    return MOCK_HEADLINES.get(symbol.upper(), DEFAULT_HEADLINES)


def detect_news_catalyst(symbol: str) -> bool:
    headlines = get_recent_headlines(symbol)
    joined = " ".join(headlines).lower()
    return any(word in joined for word in CATALYST_WORDS)


def score_news_sentiment(headlines: list[str]) -> float:
    """Score headline sentiment from 0 to 2."""
    text = " ".join(headlines).lower()
    bullish_hits = sum(1 for word in BULLISH_WORDS if word in text)
    bearish_hits = sum(1 for word in BEARISH_WORDS if word in text)

    if bullish_hits > bearish_hits:
        return 2.0
    if bearish_hits > bullish_hits:
        return 0.5
    return 1.0
