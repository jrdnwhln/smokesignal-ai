import statistics
import time
from typing import Any

import requests

from app.config import settings


MOCK_MARKET_DATA = {
    "SPY": {"price": 622.34, "price_change": 0.7, "volume_change": 1.2, "volatility": 0.8},
    "QQQ": {"price": 548.12, "price_change": 0.9, "volume_change": 1.4, "volatility": 1.1},
    "NVDA": {"price": 142.85, "price_change": 2.8, "volume_change": 3.1, "volatility": 2.6},
    "TSLA": {"price": 186.40, "price_change": -2.2, "volume_change": 2.8, "volatility": 2.4},
    "AMD": {"price": 167.75, "price_change": 1.9, "volume_change": 2.1, "volatility": 1.9},
    "AAPL": {"price": 214.06, "price_change": 0.4, "volume_change": 0.9, "volatility": 0.7},
    "META": {"price": 627.90, "price_change": 1.3, "volume_change": 1.8, "volatility": 1.4},
    "BTC": {"price": 93450.00, "price_change": 1.6, "volume_change": 2.3, "volatility": 1.8},
    "ETH": {"price": 3425.20, "price_change": 1.1, "volume_change": 1.7, "volatility": 1.5},
    "SOL": {"price": 171.80, "price_change": 3.2, "volume_change": 2.9, "volatility": 2.7},
    "XRP": {"price": 0.58, "price_change": -0.8, "volume_change": 1.3, "volatility": 1.2},
}

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
}

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
_LIVE_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_SECONDS = 60


def _symbol_data(symbol: str) -> dict[str, float]:
    return MOCK_MARKET_DATA.get(symbol.upper(), {"price": 100.0, "price_change": 0.2, "volume_change": 1.0, "volatility": 0.6})


def _is_crypto(symbol: str) -> bool:
    return symbol.upper() in COINGECKO_IDS


def _percent_change(old_value: float, new_value: float) -> float:
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def _nearest_price_from_minutes_ago(prices: list[list[float]], minutes: int) -> float | None:
    if not prices:
        return None

    target_ms = int(time.time() * 1000) - (minutes * 60 * 1000)
    nearest = min(prices, key=lambda item: abs(item[0] - target_ms))
    return float(nearest[1])


def _volume_multiple(volumes: list[list[float]]) -> float:
    if len(volumes) < 2:
        return 1.0

    latest_volume = float(volumes[-1][1])
    average_volume = sum(float(item[1]) for item in volumes[:-1]) / (len(volumes) - 1)
    if average_volume == 0:
        return 1.0
    return round(latest_volume / average_volume, 2)


def _volatility_from_prices(prices: list[list[float]]) -> float:
    if len(prices) < 3:
        return 0.6

    price_values = [float(item[1]) for item in prices[-24:]]
    returns = [
        _percent_change(price_values[index - 1], price_values[index])
        for index in range(1, len(price_values))
        if price_values[index - 1] != 0
    ]
    if len(returns) < 2:
        return 0.6

    # Scale short-window return dispersion into the 0-3-ish range expected by the MVP scorer.
    return round(min(3.0, statistics.stdev(returns) * 10), 2)


def _get_live_crypto_snapshot(symbol: str) -> dict[str, float | str] | None:
    """Try CoinGecko live crypto data, returning None if anything fails.

    CoinGecko's documented endpoints include /simple/price for current prices
    and /coins/{id}/market_chart for historical price/volume data.
    """
    symbol = symbol.upper()
    coin_id = COINGECKO_IDS.get(symbol)
    if not coin_id:
        return None

    cached = _LIVE_CACHE.get(symbol)
    if cached and time.time() - cached["fetched_at"] < _CACHE_SECONDS:
        return cached["snapshot"]

    try:
        price_response = requests.get(
            f"{COINGECKO_BASE_URL}/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
            },
            timeout=8,
        )
        price_response.raise_for_status()
        price_data = price_response.json()[coin_id]

        chart_response = requests.get(
            f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": "1"},
            timeout=8,
        )
        chart_response.raise_for_status()
        chart_data = chart_response.json()

        current_price = float(price_data["usd"])
        prices = chart_data.get("prices", [])
        volumes = chart_data.get("total_volumes", [])
        old_price = _nearest_price_from_minutes_ago(prices, minutes=15)
        price_change = _percent_change(old_price, current_price) if old_price else float(price_data.get("usd_24h_change", 0.0))

        snapshot = {
            "symbol": symbol,
            "price": round(current_price, 4),
            "price_change": round(price_change, 2),
            "volume_change": _volume_multiple(volumes),
            "volatility": _volatility_from_prices(prices),
            "data_source": "coingecko",
        }
        _LIVE_CACHE[symbol] = {"fetched_at": time.time(), "snapshot": snapshot}
        return snapshot
    except Exception as exc:
        print(f"CoinGecko data unavailable for {symbol}: {exc}. Using mock data.")
        return None


def _get_mock_snapshot(symbol: str) -> dict[str, float | str]:
    symbol = symbol.upper()
    data = _symbol_data(symbol)
    return {
        "symbol": symbol,
        "price": data["price"],
        "price_change": data["price_change"],
        "volume_change": data["volume_change"],
        "volatility": data["volatility"],
        "data_source": "mock",
    }


def get_asset_price(symbol: str) -> float:
    """Return the latest asset price.

    Future providers can be added here, such as Finnhub, Twelve Data, Polygon,
    CoinGecko, Binance, Coinbase, or another trusted market data source.
    """
    snapshot = get_market_snapshot(symbol)
    return float(snapshot["price"])


def get_recent_price_change(symbol: str, minutes: int = 15) -> float:
    """Return recent percent price change over a short window."""
    snapshot = get_market_snapshot(symbol)
    return float(snapshot["price_change"])


def get_volume_change(symbol: str) -> float:
    """Return volume multiple compared with recent average volume."""
    snapshot = get_market_snapshot(symbol)
    return float(snapshot["volume_change"])


def get_volatility_score(symbol: str) -> float:
    """Return a normalized volatility indicator for scoring."""
    snapshot = get_market_snapshot(symbol)
    return float(snapshot["volatility"])


def get_market_snapshot(symbol: str) -> dict[str, float | str]:
    """Return all market fields needed by the signal engine."""
    symbol = symbol.upper()
    if _is_crypto(symbol):
        live_snapshot = _get_live_crypto_snapshot(symbol)
        if live_snapshot:
            return live_snapshot

    # Stock data stays mocked for now. Finnhub, Twelve Data, Polygon, or IEX
    # Cloud can be added here when a stock-data API key is selected.
    return _get_mock_snapshot(symbol)
