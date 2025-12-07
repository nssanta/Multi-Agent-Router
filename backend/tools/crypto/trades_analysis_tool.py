"""
Trades Analysis Tool - расширенный анализ потока сделок
"""

import logging
from typing import Dict, Any
from datetime import datetime
from backend.tools.base import BaseTool, ToolResult, register_tool
from .trades_tool import get_recent_trades

logger = logging.getLogger(__name__)


def analyze_trades(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """
    Выполняем глубокий анализ потока сделок с расширенными метриками.
    :param symbol: Торговая пара
    :param limit: Лимит сделок
    :return: Результаты анализа сделок
    """
    trades_data = get_recent_trades(symbol, limit)
    
    if not trades_data["success"]:
        return trades_data
    
    try:
        trades = trades_data.get("trades", [])
        buy_pressure = trades_data["buy_volume_ratio"]
        
        # === Анализируем временные метрики ===
        time_metrics = {}
        if trades and len(trades) >= 2:
            # Определяем время первой и последней сделки
            first_trade_time = trades[0].get("time", 0)
            last_trade_time = trades[-1].get("time", 0)
            
            time_range_ms = last_trade_time - first_trade_time
            time_range_seconds = time_range_ms / 1000 if time_range_ms > 0 else 1
            time_range_minutes = time_range_seconds / 60
            
            # Рассчитываем скорость сделок (trades per minute)
            trades_per_minute = len(trades) / time_range_minutes if time_range_minutes > 0 else 0
            
            # Интерпретируем скорость
            if trades_per_minute > 100:
                velocity = "very_high"
                velocity_emoji = "🔥🔥"
            elif trades_per_minute > 50:
                velocity = "high"
                velocity_emoji = "🔥"
            elif trades_per_minute > 20:
                velocity = "medium"
                velocity_emoji = "➡️"
            else:
                velocity = "low"
                velocity_emoji = "💤"
            
            time_metrics = {
                "first_trade_time": datetime.fromtimestamp(first_trade_time / 1000).isoformat(),
                "last_trade_time": datetime.fromtimestamp(last_trade_time / 1000).isoformat(),
                "time_range_seconds": round(time_range_seconds, 1),
                "time_range_minutes": round(time_range_minutes, 2),
                "trades_per_minute": round(trades_per_minute, 1),
                "velocity": velocity,
                "velocity_emoji": velocity_emoji,
            }
        
        # === Анализируем распределение по размерам ===
        size_distribution = {}
        if trades:
            sizes = [t.get("qty", 0) for t in trades]
            avg_size = sum(sizes) / len(sizes)
            
            # Категоризируем сделки: small (<0.5x avg), medium (0.5-2x), large (2-5x), whale (>5x)
            small = [t for t in trades if t.get("qty", 0) < avg_size * 0.5]
            medium = [t for t in trades if avg_size * 0.5 <= t.get("qty", 0) < avg_size * 2]
            large = [t for t in trades if avg_size * 2 <= t.get("qty", 0) < avg_size * 5]
            whale = [t for t in trades if t.get("qty", 0) >= avg_size * 5]
            
            size_distribution = {
                "avg_trade_size": round(avg_size, 6),
                "small_count": len(small),
                "medium_count": len(medium),
                "large_count": len(large),
                "whale_count": len(whale),
                "small_percent": round(len(small) / len(trades) * 100, 1),
                "medium_percent": round(len(medium) / len(trades) * 100, 1),
                "large_percent": round(len(large) / len(trades) * 100, 1),
                "whale_percent": round(len(whale) / len(trades) * 100, 1),
            }
            
            # Рассчитываем объём по категориям
            small_volume = sum(t.get("qty", 0) for t in small)
            medium_volume = sum(t.get("qty", 0) for t in medium)
            large_volume = sum(t.get("qty", 0) for t in large)
            whale_volume = sum(t.get("qty", 0) for t in whale)
            total_vol = small_volume + medium_volume + large_volume + whale_volume
            
            if total_vol > 0:
                size_distribution["whale_volume_percent"] = round(whale_volume / total_vol * 100, 1)
                size_distribution["large_volume_percent"] = round(large_volume / total_vol * 100, 1)
        
        # === Оцениваем давление ===
        if buy_pressure >= 65:
            pressure = "very_strong_buy"
            pressure_emoji = "🟢🟢🟢"
        elif buy_pressure >= 55:
            pressure = "strong_buy"
            pressure_emoji = "🟢🟢"
        elif buy_pressure >= 52:
            pressure = "moderate_buy"
            pressure_emoji = "🟢"
        elif buy_pressure <= 35:
            pressure = "very_strong_sell"
            pressure_emoji = "🔴🔴🔴"
        elif buy_pressure <= 45:
            pressure = "strong_sell"
            pressure_emoji = "🔴🔴"
        elif buy_pressure <= 48:
            pressure = "moderate_sell"
            pressure_emoji = "🔴"
        else:
            pressure = "neutral"
            pressure_emoji = "⚪"
        
        # === Анализируем крупные сделки (киты) ===
        large_trades = {}
        if trades:
            avg_size = sum(t.get("qty", 0) for t in trades) / len(trades)
            whale_threshold = avg_size * 5
            whales = [t for t in trades if t.get("qty", 0) > whale_threshold]
            whale_buys = [t for t in whales if t.get("side") == "buy"]
            whale_sells = [t for t in whales if t.get("side") == "sell"]
            
            whale_buy_volume = sum(t.get("qty", 0) for t in whale_buys)
            whale_sell_volume = sum(t.get("qty", 0) for t in whale_sells)
            
            if len(whale_buys) > len(whale_sells) * 1.5:
                whale_direction = "accumulating"
                whale_emoji = "🐋🟢"
            elif len(whale_sells) > len(whale_buys) * 1.5:
                whale_direction = "distributing"
                whale_emoji = "🐋🔴"
            else:
                whale_direction = "neutral"
                whale_emoji = "🐋⚪"
            
            large_trades = {
                "count": len(whales),
                "buy_count": len(whale_buys),
                "sell_count": len(whale_sells),
                "buy_volume": round(whale_buy_volume, 6),
                "sell_volume": round(whale_sell_volume, 6),
                "whale_direction": whale_direction,
                "whale_emoji": whale_emoji,
                "threshold": round(whale_threshold, 6),
            }
        
        # === Оцениваем агрессивность ===
        # Сравниваем объёмы buy vs sell в крупных сделках
        aggressiveness = {}
        if large_trades.get("buy_volume", 0) > 0 or large_trades.get("sell_volume", 0) > 0:
            total_whale_vol = large_trades.get("buy_volume", 0) + large_trades.get("sell_volume", 0)
            if total_whale_vol > 0:
                buy_aggression = large_trades.get("buy_volume", 0) / total_whale_vol * 100
                sell_aggression = large_trades.get("sell_volume", 0) / total_whale_vol * 100
                
                aggressiveness = {
                    "buy_aggression": round(buy_aggression, 1),
                    "sell_aggression": round(sell_aggression, 1),
                    "dominant": "buyers" if buy_aggression > sell_aggression else "sellers",
                }
        
        # === Определяем тренд ===
        trend = "neutral"
        trend_emoji = "➡️"
        if buy_pressure >= 55 and large_trades.get("whale_direction") == "accumulating":
            trend = "strong_bullish"
            trend_emoji = "📈📈"
        elif buy_pressure >= 52:
            trend = "bullish"
            trend_emoji = "📈"
        elif buy_pressure <= 45 and large_trades.get("whale_direction") == "distributing":
            trend = "strong_bearish"
            trend_emoji = "📉📉"
        elif buy_pressure <= 48:
            trend = "bearish"
            trend_emoji = "📉"
        
        # === Рассчитываем коэффициенты (Ratios) ===
        ratios = {
            "buy_sell_count_ratio": round(trades_data.get("buy_count", 0) / max(trades_data.get("sell_count", 1), 1), 2),
            "buy_sell_volume_ratio": round(trades_data.get("buy_volume", 0) / max(trades_data.get("sell_volume", 0.0001), 0.0001), 2),
            "whale_buy_sell_ratio": round(large_trades.get("buy_count", 0) / max(large_trades.get("sell_count", 1), 1), 2),
        }
        
        return {
            **trades_data,
            "pressure": pressure,
            "pressure_emoji": pressure_emoji,
            "time_metrics": time_metrics,
            "size_distribution": size_distribution,
            "large_trades": large_trades,
            "aggressiveness": aggressiveness,
            "ratios": ratios,
            "whale_activity": "high" if large_trades.get("count", 0) > 10 else "medium" if large_trades.get("count", 0) > 5 else "low",
            "trend": trend,
            "trend_emoji": trend_emoji,
            "summary": f"{trend_emoji} Тренд: {trend}, {pressure_emoji} Давление: {buy_pressure:.1f}%, {time_metrics.get('velocity_emoji', '')} {time_metrics.get('trades_per_minute', 0):.0f} trades/min"
        }
    except Exception as e:
        logger.error(f"Error analyzing trades for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class TradesAnalysisTool(BaseTool):
    """
    Инструмент для расширенного анализа потока сделок.
    """
    
    name = "analyze_trades"
    description = "Расширенный анализ buy/sell pressure, whale activity, временных метрик и распределения размеров."
    
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