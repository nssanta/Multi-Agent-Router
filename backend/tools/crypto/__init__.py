"""
Crypto Tools - инструменты для анализа криптовалют (v2.0)
"""

from .binance_client import BinanceClient, get_binance_client, OHLCV, Trade, OrderBook, Ticker24h
from .klines_tool import get_klines, KlinesTool
from .trades_tool import get_recent_trades, TradesTool
from .orderbook_tool import get_orderbook, OrderbookTool
from .indicators_tool import calculate_indicators, IndicatorsTool
from .trades_analysis_tool import analyze_trades, TradesAnalysisTool
from .orderbook_analysis_tool import analyze_orderbook, OrderbookAnalysisTool

# Новые инструменты v2.0
from .futures_tool import get_funding_rate, get_futures_market_data, FundingRateTool, FuturesMarketTool
from .smart_money_tool import analyze_smart_money, SmartMoneyTool
from .mtf_analysis_tool import run_mtf_analysis, MTFAnalysisTool
from .volume_analysis_tool import analyze_volume, VolumeAnalysisTool

__all__ = [
    # Binance Client
    "BinanceClient", "get_binance_client", "OHLCV", "Trade", "OrderBook", "Ticker24h",
    # Basic Tools
    "get_klines", "KlinesTool",
    "get_recent_trades", "TradesTool",
    "get_orderbook", "OrderbookTool",
    "calculate_indicators", "IndicatorsTool",
    "analyze_trades", "TradesAnalysisTool",
    "analyze_orderbook", "OrderbookAnalysisTool",
    # New Tools v2.0
    "get_funding_rate", "get_futures_market_data", "FundingRateTool", "FuturesMarketTool",
    "analyze_smart_money", "SmartMoneyTool",
    "run_mtf_analysis", "MTFAnalysisTool",
    "analyze_volume", "VolumeAnalysisTool",
]
