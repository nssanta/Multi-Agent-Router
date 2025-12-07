"""
Trades Analysis Tool - анализ потока сделок
"""

import logging
from typing import Dict, Any
from datetime import datetime
from backend.tools.base import BaseTool, ToolResult, register_tool
from .trades_tool import get_recent_trades

logger = logging.getLogger(__name__)


def analyze_trades(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """Глубокий анализ потока сделок"""
    trades_data = get_recent_trades(symbol, limit)
    
    if not trades_data["success"]:
        return trades_data
    
    try:
        trades = trades_data.get("trades", [])
        buy_pressure = trades_data["buy_volume_ratio"]
        
        # Давление
        if buy_pressure >= 60:
            pressure = "strong_buy"
            pressure_emoji = "🟢🟢"
        elif buy_pressure >= 55:
            pressure = "moderate_buy"
            pressure_emoji = "🟢"
        elif buy_pressure <= 40:
            pressure = "strong_sell"
            pressure_emoji = "🔴🔴"
        elif buy_pressure <= 45:
            pressure = "moderate_sell"
            pressure_emoji = "🔴"
        else:
            pressure = "neutral"
            pressure_emoji = "⚪"
        
        # Крупные сделки
        large_trades = {}
        if trades:
            avg_size = sum(t["qty"] for t in trades) / len(trades)
            large = [t for t in trades if t["qty"] > avg_size * 5]
            large_buys = [t for t in large if t["side"] == "buy"]
            large_sells = [t for t in large if t["side"] == "sell"]
            large_trades = {
                "count": len(large),
                "buy_count": len(large_buys),
                "sell_count": len(large_sells),
                "whale_direction": "buy" if len(large_buys) > len(large_sells) else "sell",
            }
        
        # Тренд
        trend = "neutral"
        trend_emoji = "➡️"
        if buy_pressure >= 55:
            trend = "bullish"
            trend_emoji = "📈"
        elif buy_pressure <= 45:
            trend = "bearish"
            trend_emoji = "📉"
        
        return {
            **trades_data,
            "pressure": pressure,
            "pressure_emoji": pressure_emoji,
            "large_trades": large_trades,
            "whale_activity": "high" if large_trades.get("count", 0) > 10 else "low",
            "trend": trend,
            "trend_emoji": trend_emoji,
            "summary": f"{trend_emoji} Тренд: {trend}, {pressure_emoji} Давление: {buy_pressure:.1f}%"
        }
    except Exception as e:
        logger.error(f"Error analyzing trades for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class TradesAnalysisTool(BaseTool):
    """Инструмент для анализа потока сделок"""
    
    name = "analyze_trades"
    description = "Анализ buy/sell pressure и whale activity."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "limit": {"type": "integer", "description": "Количество сделок", "default": 1000}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, limit: int = 1000, **kwargs) -> ToolResult:
        result = analyze_trades(symbol, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)
