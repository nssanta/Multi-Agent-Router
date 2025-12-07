"""
Indicators Tool - расчёт технических индикаторов (stub без pandas-ta)
"""

import logging
from typing import Dict, List, Any
from backend.tools.base import BaseTool, ToolResult, register_tool

logger = logging.getLogger(__name__)

# Проверяем наличие pandas-ta
try:
    import pandas as pd
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    logger.warning("pandas-ta not installed")


def calculate_indicators(ohlcv_data: Dict[str, List], indicators: List[str] = None) -> Dict[str, Any]:
    """Расчёт технических индикаторов"""
    if not PANDAS_TA_AVAILABLE:
        return {"success": False, "error": "pandas-ta not installed"}
    
    if indicators is None:
        indicators = ["rsi", "macd", "ema"]
    
    try:
        df = pd.DataFrame({
            "open": ohlcv_data["open"],
            "high": ohlcv_data["high"],
            "low": ohlcv_data["low"],
            "close": ohlcv_data["close"],
            "volume": ohlcv_data["volume"],
        })
        
        results = {
            "success": True,
            "current_price": df["close"].iloc[-1],
            "indicators": {},
            "signals": [],
            "overall_signal": "neutral",
        }
        
        bullish_count = 0
        bearish_count = 0
        
        # RSI
        if "rsi" in indicators:
            rsi = ta.rsi(df["close"], length=14)
            if rsi is not None and len(rsi) > 0:
                current_rsi = rsi.iloc[-1]
                signal = "neutral"
                if current_rsi < 30:
                    signal = "oversold"
                    bullish_count += 1
                elif current_rsi > 70:
                    signal = "overbought"
                    bearish_count += 1
                results["indicators"]["rsi"] = {"value": round(current_rsi, 2), "signal": signal}
        
        # MACD
        if "macd" in indicators:
            macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd is not None and len(macd) > 0:
                macd_line = macd.iloc[-1, 0]
                signal_line = macd.iloc[-1, 1]
                signal = "bullish" if macd_line > signal_line else "bearish"
                if signal == "bullish":
                    bullish_count += 1
                else:
                    bearish_count += 1
                results["indicators"]["macd"] = {"macd": round(macd_line, 4), "trend": signal}
        
        # EMA
        if "ema" in indicators:
            ema_9 = ta.ema(df["close"], length=9)
            ema_21 = ta.ema(df["close"], length=21)
            if ema_9 is not None and ema_21 is not None:
                results["indicators"]["ema"] = {
                    "ema_9": round(ema_9.iloc[-1], 2),
                    "ema_21": round(ema_21.iloc[-1], 2),
                }
        
        # Общий сигнал
        if bullish_count > bearish_count:
            results["overall_signal"] = "bullish"
        elif bearish_count > bullish_count:
            results["overall_signal"] = "bearish"
        
        results["bullish_count"] = bullish_count
        results["bearish_count"] = bearish_count
        
        return results
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return {"success": False, "error": str(e)}


@register_tool
class IndicatorsTool(BaseTool):
    """Инструмент для расчёта технических индикаторов"""
    
    name = "calculate_indicators"
    description = "Рассчитать технические индикаторы (RSI, MACD, EMA)."
    
    parameters = {
        "ohlcv_data": {"type": "object", "description": "OHLCV данные"},
        "indicators": {"type": "array", "description": "Список индикаторов"}
    }
    
    required_params = ["ohlcv_data"]
    agent_types = ["crypto"]
    
    def execute(self, ohlcv_data: Dict[str, List], indicators: List[str] = None, **kwargs) -> ToolResult:
        result = calculate_indicators(ohlcv_data, indicators)
        if result["success"]:
            return ToolResult.success(data=result, message=f"Signal: {result['overall_signal']}")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)
