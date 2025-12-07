"""
Trades Tool - получение последних сделок с Binance
"""

import logging
from typing import Dict, Any
from backend.tools.base import BaseTool, ToolResult, register_tool
from .binance_client import get_binance_client

logger = logging.getLogger(__name__)


def get_recent_trades(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """Получить последние сделки"""
    try:
        client = get_binance_client()
        trades = client.get_recent_trades(symbol, limit)
        
        if not trades:
            return {"success": False, "error": f"No trades for {symbol}", "symbol": symbol}
        
        buy_trades = [t for t in trades if t.is_buy]
        sell_trades = [t for t in trades if not t.is_buy]
        
        total_volume = sum(t.qty for t in trades)
        buy_volume = sum(t.qty for t in buy_trades)
        sell_volume = sum(t.qty for t in sell_trades)
        
        return {
            "success": True,
            "symbol": client.normalize_symbol(symbol),
            "total_trades": len(trades),
            "buy_count": len(buy_trades),
            "sell_count": len(sell_trades),
            "buy_volume": round(buy_volume, 6),
            "sell_volume": round(sell_volume, 6),
            "total_volume": round(total_volume, 6),
            "buy_quote_volume": round(sum(t.quote_qty for t in buy_trades), 2),
            "sell_quote_volume": round(sum(t.quote_qty for t in sell_trades), 2),
            "buy_ratio": round(len(buy_trades) / len(trades) * 100, 1) if trades else 0,
            "sell_ratio": round(len(sell_trades) / len(trades) * 100, 1) if trades else 0,
            "buy_volume_ratio": round(buy_volume / total_volume * 100, 1) if total_volume > 0 else 0,
            "current_price": trades[-1].price,
            "avg_price": round(sum(t.quote_qty for t in trades) / total_volume, 2) if total_volume > 0 else 0,
            "trades": [t.to_dict() for t in trades[-100:]],
        }
    except Exception as e:
        logger.error(f"Error getting trades for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class TradesTool(BaseTool):
    """Инструмент для получения последних сделок"""
    
    name = "get_recent_trades"
    description = "Получить последние сделки с Binance с разделением на buy/sell."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "limit": {"type": "integer", "description": "Количество сделок (max 1000)", "default": 1000}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, limit: int = 1000, **kwargs) -> ToolResult:
        result = get_recent_trades(symbol, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=f"Получено {result['total_trades']} сделок")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)
