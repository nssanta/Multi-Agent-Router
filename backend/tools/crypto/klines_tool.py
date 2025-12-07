"""
Klines Tool - получение свечей с Binance
"""

import logging
from typing import Dict, List, Any
from backend.tools.base import BaseTool, ToolResult, register_tool
from .binance_client import get_binance_client

logger = logging.getLogger(__name__)


def get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
    """Получить свечи для символа"""
    try:
        client = get_binance_client()
        klines = client.get_klines(symbol, interval, limit)
        
        if not klines:
            return {"success": False, "error": f"No klines data for {symbol}", "symbol": symbol, "interval": interval}
        
        return {
            "success": True,
            "symbol": client.normalize_symbol(symbol),
            "interval": interval,
            "count": len(klines),
            "first_candle": klines[0].datetime.isoformat(),
            "last_candle": klines[-1].datetime.isoformat(),
            "current_price": klines[-1].close,
            "high_24h": max(k.high for k in klines[-24:]) if len(klines) >= 24 else max(k.high for k in klines),
            "low_24h": min(k.low for k in klines[-24:]) if len(klines) >= 24 else min(k.low for k in klines),
            "candles": [k.to_dict() for k in klines],
            "ohlcv": {
                "timestamps": [k.timestamp for k in klines],
                "open": [k.open for k in klines],
                "high": [k.high for k in klines],
                "low": [k.low for k in klines],
                "close": [k.close for k in klines],
                "volume": [k.volume for k in klines],
            }
        }
    except Exception as e:
        logger.error(f"Error getting klines for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol, "interval": interval}


@register_tool
class KlinesTool(BaseTool):
    """Инструмент для получения свечей с Binance"""
    
    name = "get_klines"
    description = "Получить свечи (candlesticks) с Binance для технического анализа."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара (BTC, ETH, BTCUSDT)"},
        "interval": {"type": "string", "description": "Интервал (5m, 1h, 4h, 1d)", "default": "1h"},
        "limit": {"type": "integer", "description": "Количество свечей (max 1000)", "default": 100}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, interval: str = "1h", limit: int = 100, **kwargs) -> ToolResult:
        result = get_klines(symbol, interval, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=f"Получено {result['count']} свечей")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)
