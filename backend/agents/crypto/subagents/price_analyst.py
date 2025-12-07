"""
Price Analyst - анализ цены и индикаторов
"""

from typing import Dict, Any
from backend.tools.crypto.klines_tool import get_klines
from backend.tools.crypto.indicators_tool import calculate_indicators
from backend.tools.crypto.binance_client import get_binance_client


def run_price_analysis(symbol: str, timeframes: list = None) -> Dict[str, Any]:
    """Выполнить анализ цены и индикаторов"""
    if timeframes is None:
        timeframes = ["5m", "1h", "4h", "1d"]
    
    try:
        client = get_binance_client()
        normalized_symbol = client.normalize_symbol(symbol)
        ticker = client.get_ticker_24h(normalized_symbol)
        
        result = {
            "success": True,
            "symbol": normalized_symbol,
            "current_price": ticker.last_price,
            "price_change_24h": ticker.price_change,
            "price_change_percent_24h": ticker.price_change_percent,
            "high_24h": ticker.high_price,
            "low_24h": ticker.low_price,
            "volume_24h": ticker.volume,
            "timeframe_analysis": {},
        }
        
        for tf in timeframes:
            klines_data = get_klines(normalized_symbol, tf, limit=100)
            if klines_data["success"]:
                indicators = calculate_indicators(klines_data["ohlcv"])
                if indicators["success"]:
                    result["timeframe_analysis"][tf] = {
                        "indicators": indicators["indicators"],
                        "overall_signal": indicators["overall_signal"],
                        "bullish_count": indicators["bullish_count"],
                        "bearish_count": indicators["bearish_count"],
                    }
        
        # Общий анализ
        bullish_tfs = sum(1 for tf_data in result["timeframe_analysis"].values() 
                         if tf_data.get("overall_signal") == "bullish")
        bearish_tfs = sum(1 for tf_data in result["timeframe_analysis"].values() 
                         if tf_data.get("overall_signal") == "bearish")
        
        if bullish_tfs > bearish_tfs + 1:
            result["overall_trend"] = "bullish"
            result["trend_emoji"] = "📈"
        elif bearish_tfs > bullish_tfs + 1:
            result["overall_trend"] = "bearish"
            result["trend_emoji"] = "📉"
        else:
            result["overall_trend"] = "neutral"
            result["trend_emoji"] = "➡️"
        
        result["bullish_timeframes"] = bullish_tfs
        result["bearish_timeframes"] = bearish_tfs
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "symbol": symbol}
