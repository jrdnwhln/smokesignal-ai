from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import requests

from app.config import settings


GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
NEWS_CACHE_SECONDS = 300
_NEWS_CACHE: dict[str, dict[str, Any]] = {}

MOCK_ARTICLES = {
    "NVDA": [
        {
            "title": "Nvidia shares rise as AI chip demand remains strong",
            "source": "Mock Market Desk",
            "url": "",
            "published_at": "",
            "summary": "Analysts point to fresh data center momentum for Nvidia.",
            "data_source": "mock",
        },
    ],
    "TSLA": [
        {
            "title": "Tesla slips after production concerns weigh on sentiment",
            "source": "Mock Market Desk",
            "url": "",
            "published_at": "",
            "summary": "EV sector traders are watching pricing updates and delivery commentary.",
            "data_source": "mock",
        },
    ],
    "SOL": [
        {
            "title": "Solana gains as on-chain activity jumps and exchange volume expands",
            "source": "Mock Crypto Desk",
            "url": "",
            "published_at": "",
            "summary": "Crypto traders are watching Solana after network activity improved.",
            "data_source": "mock",
        },
    ],
    "BTC": [
        {
            "title": "Bitcoin holds near recent highs as ETF flows stay in focus",
            "source": "Mock Crypto Desk",
            "url": "",
            "published_at": "",
            "summary": "Macro traders are watching Bitcoin ahead of Fed commentary.",
            "data_source": "mock",
        },
    ],
}

DEFAULT_ARTICLES = [
    {
        "title": "Markets trade mixed as investors wait for fresh economic data",
        "source": "Mock Market Desk",
        "url": "",
        "published_at": "",
        "summary": "Sector rotation continues while volume stays near average.",
        "data_source": "mock",
    },
]

BULLISH_WORDS = {
    "beat",
    "beats",
    "breakout",
    "bullish",
    "demand",
    "gain",
    "gains",
    "highs",
    "jump",
    "jumps",
    "momentum",
    "raise",
    "raises",
    "rally",
    "rise",
    "rises",
    "strong",
    "surge",
    "upgrade",
}
BEARISH_WORDS = {
    "bearish",
    "concerns",
    "cut",
    "cuts",
    "downgrade",
    "fall",
    "falls",
    "lawsuit",
    "miss",
    "probe",
    "risk",
    "selloff",
    "slips",
    "weak",
    "weigh",
}
CATALYST_WORDS = {
    "approval",
    "announcement",
    "cpi",
    "demand",
    "earnings",
    "etf",
    "fed",
    "filing",
    "flows",
    "forecast",
    "guidance",
    "inflation",
    "launch",
    "merger",
    "partnership",
    "production",
    "rate",
    "sec",
    "upgrade",
}


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _published_at(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def _build_news_query(symbol: str) -> str:
    symbol = symbol.upper()
    crypto_symbols = {"BTC", "ETH", "SOL", "XRP"}
    forex_symbols = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"}

    if symbol in crypto_symbols:
        return f"{symbol} crypto market OR price OR exchange announcement"
    if symbol in forex_symbols:
        return f"{symbol} forex market OR central bank OR rate"
    return f"{symbol} stock OR shares OR earnings OR SEC filing"


def _parse_google_news_rss(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    articles = []

    for item in root.findall(".//item")[:8]:
        title = _clean_text(item.findtext("title"))
        source_node = item.find("source")
        source = _clean_text(source_node.text if source_node is not None else "")
        description = _clean_text(item.findtext("description"))

        articles.append(
            {
                "title": title,
                "source": source or "Google News",
                "url": item.findtext("link") or "",
                "published_at": _published_at(item.findtext("pubDate")),
                "summary": description,
                "data_source": "google_news_rss",
            }
        )

    return articles


def get_recent_articles(symbol: str) -> list[dict[str, str]]:
    """Return recent market articles with source info.

    This MVP uses Google News RSS search as a free public discovery layer. Later,
    production-grade source monitoring can add SEC EDGAR, company press releases,
    earnings calendars, Fed releases, crypto exchange announcements, and paid
    finance/news APIs with stricter source allowlists.
    """
    symbol = symbol.upper()
    cached = _NEWS_CACHE.get(symbol)
    if cached and time.time() - cached["fetched_at"] < NEWS_CACHE_SECONDS:
        return cached["articles"]

    if settings.NEWS_API_KEY:
        # Add a trusted paid news API here later. Keep the same output fields.
        pass

    query = quote_plus(_build_news_query(symbol))
    try:
        response = requests.get(
            GOOGLE_NEWS_RSS_URL,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=10,
            headers={"User-Agent": "SmokeSignalAI/0.1 market-monitoring-prototype"},
        )
        response.raise_for_status()
        articles = _parse_google_news_rss(response.text)
        if articles:
            _NEWS_CACHE[symbol] = {"fetched_at": time.time(), "articles": articles}
            return articles
    except Exception as exc:
        print(f"Live news unavailable for {symbol}: {exc}. Using mock headlines.")

    articles = MOCK_ARTICLES.get(symbol, DEFAULT_ARTICLES)
    _NEWS_CACHE[symbol] = {"fetched_at": time.time(), "articles": articles}
    return articles


def get_recent_headlines(symbol: str) -> list[str]:
    """Return recent headline strings for scoring."""
    return [article["title"] for article in get_recent_articles(symbol)]


def detect_news_catalyst(symbol: str) -> bool:
    articles = get_recent_articles(symbol)
    joined = " ".join(
        f"{article.get('title', '')} {article.get('summary', '')}" for article in articles
    ).lower()
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
