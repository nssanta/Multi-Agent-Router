"""
Orderbook Analysis Tool - анализ стакана заявок
"""

import logging
from typing import Dict, Any
from datetime import datetime
from backend.tools.base import BaseTool, ToolResult, register_tool
from .orderbook_tool import get_orderbook

logger = logging.getLogger(__name__)


def analyze_orderbook(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """Глубокий анализ стакана"""
    orderbook_data = get_orderbook(symbol, limit)
    
    if not orderbook_data["success"]:
        return orderbook_data
    
    try:
        deltas = orderbook_data["deltas"]
        
        bullish_levels = sum(1 for d in deltas.values() if d["pressure"] == "buy")
        bearish_levels = len(deltas) - bullish_levels
        
        # Sentiment
        if bullish_levels >= 3:
            sentiment = "bullish"
            sentiment_emoji = "🟢🟢"
        elif bullish_levels >= 2:
            sentiment = "slightly_bullish"
            sentiment_emoji = "🟢"
        elif bearish_levels >= 3:
            sentiment = "bearish"
            sentiment_emoji = "🔴🔴"
        elif bearish_levels >= 2:
            sentiment = "slightly_bearish"
            sentiment_emoji = "🔴"
        else:
            sentiment = "neutral"
            sentiment_emoji = "⚪"
        
        # Глубина
        bid_ask_ratio = orderbook_data["bid_ask_ratio"]
        if bid_ask_ratio >= 1.5:
            depth_analysis = "strong_bid_wall"
            depth_emoji = "🟢🧱"
        elif bid_ask_ratio <= 0.67:
            depth_analysis = "strong_ask_wall"
            depth_emoji = "🔴🧱"
        else:
            depth_analysis = "balanced"
            depth_emoji = "⚖️"
        
        # Таблица дельт
        delta_table = "| Уровень | Bid | Ask | Давление |\n|---------|-----|-----|----------|\n"
        for level, d in deltas.items():
            emoji = "🟢" if d["pressure"] == "buy" else "🔴"
            delta_table += f"| {level} | {d['bid_volume']:.2f} | {d['ask_volume']:.2f} | {emoji} |\n"
        
        # Уровни
        supports = orderbook_data["support_levels"][:3]
        resistances = orderbook_data["resistance_levels"][:3]
        support_prices = ", ".join(f"${s.get('price', 0):.0f}" for s in supports)
        resistance_prices = ", ".join(f"${r.get('price', 0):.0f}" for r in resistances)
        levels_text = f"🟢 Поддержка: {support_prices}\n🔴 Сопротивление: {resistance_prices}"
        
        return {
            **orderbook_data,
            "sentiment": sentiment,
            "sentiment_emoji": sentiment_emoji,
            "bullish_levels": bullish_levels,
            "bearish_levels": bearish_levels,
            "depth_analysis": depth_analysis,
            "depth_emoji": depth_emoji,
            "delta_table": delta_table,
            "levels_text": levels_text,
            "summary": f"{sentiment_emoji} Sentiment: {sentiment}, {depth_emoji} Глубина: {depth_analysis}"
        }
    except Exception as e:
        logger.error(f"Error analyzing orderbook for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class OrderbookAnalysisTool(BaseTool):
    """Инструмент для анализа стакана"""
    
    name = "analyze_orderbook"
    description = "Анализ дельт стакана и уровней поддержки/сопротивления."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "limit": {"type": "integer", "description": "Глубина стакана", "default": 1000}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, limit: int = 1000, **kwargs) -> ToolResult:
        result = analyze_orderbook(symbol, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)
