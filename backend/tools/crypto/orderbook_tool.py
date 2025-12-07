"""
Orderbook Tool - получение стакана с Binance
"""

import logging
from typing import Dict, List, Any, Tuple
from backend.tools.base import BaseTool, ToolResult, register_tool
from .binance_client import get_binance_client, OrderBook

logger = logging.getLogger(__name__)


def calculate_delta_at_level(orderbook: OrderBook, price: float, percent: float) -> Dict[str, Any]:
    """
    Рассчитываем дельту на ценовом уровне.
    :param orderbook: Данные стакана
    :param price: Текущая цена
    :param percent: Процент отклонения от цены
    :return: Результаты анализа дельты
    """
    lower_bound = price * (1 - percent / 100)
    upper_bound = price * (1 + percent / 100)
    
    bid_volume = sum(qty for price_level, qty in orderbook.bids if price_level >= lower_bound)
    ask_volume = sum(qty for price_level, qty in orderbook.asks if price_level <= upper_bound)
    delta = bid_volume - ask_volume
    
    return {
        "percent": percent,
        "bid_volume": round(bid_volume, 4),
        "ask_volume": round(ask_volume, 4),
        "delta": round(delta, 4),
        "pressure": "buy" if delta > 0 else "sell",
        "imbalance_ratio": round(bid_volume / ask_volume, 2) if ask_volume > 0 else float('inf'),
    }


def find_support_resistance(orderbook: OrderBook, num_levels: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    Находим уровни поддержки и сопротивления на основе стакана.
    :param orderbook: Данные стакана
    :param num_levels: Количество уровней для поиска
    :return: Списки уровней поддержки и сопротивления
    """
    sorted_bids = sorted(orderbook.bids, key=lambda x: x[1], reverse=True)
    sorted_asks = sorted(orderbook.asks, key=lambda x: x[1], reverse=True)
    
    support = [{"price": round(p, 2), "volume": round(v, 4)} for p, v in sorted_bids[:num_levels]]
    resistance = [{"price": round(p, 2), "volume": round(v, 4)} for p, v in sorted_asks[:num_levels]]
    
    support.sort(key=lambda x: x["price"], reverse=True)
    resistance.sort(key=lambda x: x["price"])
    
    return support, resistance


def get_orderbook(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """
    Получаем стакан с расчётом дельт и уровней.
    :param symbol: Торговая пара
    :param limit: Глубина стакана
    :return: Данные стакана с аналитикой
    """
    try:
        client = get_binance_client()
        orderbook = client.get_order_book(symbol, limit)
        
        if not orderbook.bids or not orderbook.asks:
            return {"success": False, "error": f"Empty orderbook for {symbol}", "symbol": symbol}
        
        current_price = orderbook.mid_price
        
        deltas = {}
        for level in [1.5, 3, 5, 15, 30, 60, 90]:
            deltas[f"{level}%"] = calculate_delta_at_level(orderbook, current_price, level)
        
        total_bid = sum(qty for _, qty in orderbook.bids)
        total_ask = sum(qty for _, qty in orderbook.asks)
        support, resistance = find_support_resistance(orderbook)
        
        return {
            "success": True,
            "symbol": client.normalize_symbol(symbol),
            "current_price": round(current_price, 2),
            "best_bid": round(orderbook.best_bid, 2),
            "best_ask": round(orderbook.best_ask, 2),
            "spread": round(orderbook.spread, 4),
            "spread_percent": round(orderbook.spread_percent, 4),
            "total_bid_volume": round(total_bid, 4),
            "total_ask_volume": round(total_ask, 4),
            "total_delta": round(total_bid - total_ask, 4),
            "bid_ask_ratio": round(total_bid / total_ask, 2) if total_ask > 0 else 0,
            "deltas": deltas,
            "support_levels": support,
            "resistance_levels": resistance,
        }
    except Exception as e:
        logger.error(f"Error getting orderbook for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class OrderbookTool(BaseTool):
    """
    Инструмент для получения стакана.
    """
    
    name = "get_orderbook"
    description = "Получить стакан заявок с Binance с расчётом дельт."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "limit": {"type": "integer", "description": "Глубина стакана", "default": 1000}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, limit: int = 1000, **kwargs) -> ToolResult:
        result = get_orderbook(symbol, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=f"Стакан {result['symbol']}: Bid/Ask = {result['bid_ask_ratio']}")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)