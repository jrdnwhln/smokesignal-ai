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


def _symbol_data(symbol: str) -> dict[str, float]:
    return MOCK_MARKET_DATA.get(symbol.upper(), {"price": 100.0, "price_change": 0.2, "volume_change": 1.0, "volatility": 0.6})


def get_asset_price(symbol: str) -> float:
    """Return the latest asset price.

    Future providers can be added here, such as Finnhub, Twelve Data, Polygon,
    CoinGecko, Binance, Coinbase, or another trusted market data source.
    """
    if settings.MARKET_DATA_API_KEY:
        # Add real provider call here later.
        pass
    return _symbol_data(symbol)["price"]


def get_recent_price_change(symbol: str, minutes: int = 15) -> float:
    """Return recent percent price change over a short window."""
    if settings.MARKET_DATA_API_KEY:
        # Add real intraday candle comparison here later.
        pass
    return _symbol_data(symbol)["price_change"]


def get_volume_change(symbol: str) -> float:
    """Return volume multiple compared with recent average volume."""
    if settings.MARKET_DATA_API_KEY:
        # Add real volume average comparison here later.
        pass
    return _symbol_data(symbol)["volume_change"]


def get_volatility_score(symbol: str) -> float:
    """Return a normalized volatility indicator for scoring."""
    if settings.MARKET_DATA_API_KEY:
        # Add ATR, realized volatility, or candle range logic here later.
        pass
    return _symbol_data(symbol)["volatility"]


def get_market_snapshot(symbol: str) -> dict[str, float | str]:
    """Return all market fields needed by the signal engine."""
    symbol = symbol.upper()
    return {
        "symbol": symbol,
        "price": get_asset_price(symbol),
        "price_change": get_recent_price_change(symbol),
        "volume_change": get_volume_change(symbol),
        "volatility": get_volatility_score(symbol),
    }
