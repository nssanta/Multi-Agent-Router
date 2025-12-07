"""
Smart Money Concepts Tool - FVG, Order Blocks, Market Structure

Включает:
- Fair Value Gaps (FVG) - имбалансы
- Order Blocks (OB) - зоны накопления
- Market Structure (HH/HL/LL/LH) - структура рынка
- Break of Structure (BOS)
- Change of Character (CHoCH)
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from backend.tools.base import BaseTool, ToolResult, register_tool
from .klines_tool import get_klines

logger = logging.getLogger(__name__)


def find_swing_points(highs: List[float], lows: List[float], lookback: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    Находим точки Swing High и Swing Low.
    :param highs: Список максимумов
    :param lows: Список минимумов
    :param lookback: Период для поиска
    :return: Кортежи списков точек Swing High и Swing Low
    """
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, len(highs) - lookback):
        # Проверяем Swing High: текущий high выше, чем все соседние
        is_swing_high = all(highs[i] >= highs[i-j] for j in range(1, lookback+1)) and \
                        all(highs[i] >= highs[i+j] for j in range(1, lookback+1))
        
        if is_swing_high:
            swing_highs.append({"index": i, "price": highs[i]})
        
        # Проверяем Swing Low: текущий low ниже, чем все соседние
        is_swing_low = all(lows[i] <= lows[i-j] for j in range(1, lookback+1)) and \
                       all(lows[i] <= lows[i+j] for j in range(1, lookback+1))
        
        if is_swing_low:
            swing_lows.append({"index": i, "price": lows[i]})
    
    return swing_highs, swing_lows


def analyze_market_structure(swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict[str, Any]:
    """
    Анализируем структуру рынка (HH, HL, LL, LH).
    :param swing_highs: Список точек Swing High
    :param swing_lows: Список точек Swing Low
    :return: Словарь с анализом структуры рынка
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"structure": "undefined", "trend": "neutral"}
    
    # Берем последние 4 swing points
    recent_highs = sorted(swing_highs, key=lambda x: x["index"])[-4:]
    recent_lows = sorted(swing_lows, key=lambda x: x["index"])[-4:]
    
    structure_points = []
    
    # Определяем HH/LH для максимумов
    for i in range(1, len(recent_highs)):
        prev = recent_highs[i-1]
        curr = recent_highs[i]
        if curr["price"] > prev["price"]:
            structure_points.append({"type": "HH", "index": curr["index"], "price": curr["price"]})
        else:
            structure_points.append({"type": "LH", "index": curr["index"], "price": curr["price"]})
    
    # Определяем HL/LL для минимумов
    for i in range(1, len(recent_lows)):
        prev = recent_lows[i-1]
        curr = recent_lows[i]
        if curr["price"] > prev["price"]:
            structure_points.append({"type": "HL", "index": curr["index"], "price": curr["price"]})
        else:
            structure_points.append({"type": "LL", "index": curr["index"], "price": curr["price"]})
    
    # Сортируем точки структуры по индексу
    structure_points.sort(key=lambda x: x["index"])
    
    # Подсчитываем количество HH, HL, LH, LL для определения тренда
    hh_count = sum(1 for p in structure_points if p["type"] == "HH")
    hl_count = sum(1 for p in structure_points if p["type"] == "HL")
    lh_count = sum(1 for p in structure_points if p["type"] == "LH")
    ll_count = sum(1 for p in structure_points if p["type"] == "LL")
    
    if hh_count >= 2 and hl_count >= 1:
        trend = "bullish"
        structure = "uptrend"
        emoji = "📈"
    elif ll_count >= 2 and lh_count >= 1:
        trend = "bearish"
        structure = "downtrend"
        emoji = "📉"
    else:
        trend = "neutral"
        structure = "ranging"
        emoji = "↔️"
    
    return {
        "structure": structure,
        "trend": trend,
        "trend_emoji": emoji,
        "structure_points": structure_points[-6:],  # Последние 6 точек
        "hh_count": hh_count,
        "hl_count": hl_count,
        "lh_count": lh_count,
        "ll_count": ll_count,
    }


def find_fair_value_gaps(opens: List[float], highs: List[float], lows: List[float], 
                          closes: List[float], min_gap_percent: float = 0.1) -> List[Dict]:
    """
    Находим Fair Value Gaps (имбалансы).
    FVG = когда high свечи N-1 < low свечи N+1 (bullish)
       или low свечи N-1 > high свечи N+1 (bearish).
    :param opens: Цены открытия
    :param highs: Цены максимума
    :param lows: Цены минимума
    :param closes: Цены закрытия
    :param min_gap_percent: Минимальный размер гэпа в процентах
    :return: Список найденных имбалансов
    """
    fvgs = []
    
    for i in range(1, len(highs) - 1):
        # Проверяем Bullish FVG: high[i-1] < low[i+1]
        if highs[i-1] < lows[i+1]:
            gap_size = lows[i+1] - highs[i-1]
            gap_percent = (gap_size / closes[i]) * 100
            
            if gap_percent >= min_gap_percent:
                fvgs.append({
                    "type": "bullish",
                    "index": i,
                    "top": lows[i+1],
                    "bottom": highs[i-1],
                    "gap_size": round(gap_size, 4),
                    "gap_percent": round(gap_percent, 3),
                    "filled": False,
                    "emoji": "🟢"
                })
        
        # Проверяем Bearish FVG: low[i-1] > high[i+1]
        if lows[i-1] > highs[i+1]:
            gap_size = lows[i-1] - highs[i+1]
            gap_percent = (gap_size / closes[i]) * 100
            
            if gap_percent >= min_gap_percent:
                fvgs.append({
                    "type": "bearish",
                    "index": i,
                    "top": lows[i-1],
                    "bottom": highs[i+1],
                    "gap_size": round(gap_size, 4),
                    "gap_percent": round(gap_percent, 3),
                    "filled": False,
                    "emoji": "🔴"
                })
    
    # Проверяем, заполнены ли FVG текущей ценой
    current_price = closes[-1] if closes else 0
    for fvg in fvgs:
        if fvg["type"] == "bullish" and current_price <= fvg["top"]:
            fvg["filled"] = current_price <= fvg["bottom"]
        elif fvg["type"] == "bearish" and current_price >= fvg["bottom"]:
            fvg["filled"] = current_price >= fvg["top"]
    
    return fvgs[-10:]  # Последние 10 FVG


def find_order_blocks(opens: List[float], highs: List[float], lows: List[float],
                       closes: List[float], volumes: List[float]) -> List[Dict]:
    """
    Находим Order Blocks - последняя противоположная свеча перед импульсом.
    :param opens: Цены открытия
    :param highs: Цены максимума
    :param lows: Цены минимума
    :param closes: Цены закрытия
    :param volumes: Объемы торгов
    :return: Список Order Blocks
    """
    order_blocks = []
    
    # Определяем средний размер свечи для фильтрации импульсов
    candle_sizes = [abs(closes[i] - opens[i]) for i in range(len(closes))]
    avg_candle_size = sum(candle_sizes) / len(candle_sizes) if candle_sizes else 0
    
    for i in range(2, len(closes) - 2):
        current_candle = closes[i] - opens[i]
        next_candle = closes[i+1] - opens[i+1]
        
        # Bullish Order Block: медвежья свеча, за которой следует сильный рост
        if current_candle < 0 and next_candle > avg_candle_size * 2:
            order_blocks.append({
                "type": "bullish",
                "index": i,
                "high": highs[i],
                "low": lows[i],
                "volume": volumes[i],
                "emoji": "🟢🧱",
                "description": "Зона поддержки (Bullish OB)"
            })
        
        # Bearish Order Block: бычья свеча, за которой следует сильное падение
        if current_candle > 0 and next_candle < -avg_candle_size * 2:
            order_blocks.append({
                "type": "bearish",
                "index": i,
                "high": highs[i],
                "low": lows[i],
                "volume": volumes[i],
                "emoji": "🔴🧱",
                "description": "Зона сопротивления (Bearish OB)"
            })
    
    return order_blocks[-10:]  # Последние 10 OB


def find_liquidity_zones(swing_highs: List[Dict], swing_lows: List[Dict], 
                          current_price: float) -> Dict[str, List]:
    """
    Находим зоны ликвидности (над swing highs и под swing lows).
    :param swing_highs: Список точек Swing High
    :param swing_lows: Список точек Swing Low
    :param current_price: Текущая цена
    :return: Словарь с зонами ликвидности (buy_stops, sell_stops)
    """
    
    # Определяем зоны над хаями (стоп-лоссы шортов)
    buy_stops = []
    for sh in swing_highs[-5:]:
        if sh["price"] > current_price:
            buy_stops.append({
                "price": round(sh["price"], 2),
                "distance_percent": round((sh["price"] - current_price) / current_price * 100, 2),
                "type": "buy_stops"
            })
    
    # Определяем зоны под лоями (стоп-лоссы лонгов)
    sell_stops = []
    for sl in swing_lows[-5:]:
        if sl["price"] < current_price:
            sell_stops.append({
                "price": round(sl["price"], 2),
                "distance_percent": round((current_price - sl["price"]) / current_price * 100, 2),
                "type": "sell_stops"
            })
    
    # Сортируем зоны по близости к текущей цене
    buy_stops.sort(key=lambda x: x["distance_percent"])
    sell_stops.sort(key=lambda x: x["distance_percent"])
    
    return {
        "buy_stops": buy_stops[:3],
        "sell_stops": sell_stops[:3],
    }


def analyze_smart_money(symbol: str, interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
    """
    Выполняем полный Smart Money анализ.
    :param symbol: Торговая пара
    :param interval: Интервал
    :param limit: Лимит свечей
    :return: Результаты полного анализа SMC
    """
    klines_data = get_klines(symbol, interval, limit)
    
    if not klines_data["success"]:
        return klines_data
    
    try:
        ohlcv = klines_data["ohlcv"]
        opens = ohlcv["open"]
        highs = ohlcv["high"]
        lows = ohlcv["low"]
        closes = ohlcv["close"]
        volumes = ohlcv["volume"]
        
        current_price = closes[-1] if closes else 0
        
        # 1. Находим Swing Points
        swing_highs, swing_lows = find_swing_points(highs, lows, lookback=3)
        
        # 2. Анализируем структуру рынка
        structure = analyze_market_structure(swing_highs, swing_lows)
        
        # 3. Находим Fair Value Gaps
        fvgs = find_fair_value_gaps(opens, highs, lows, closes, min_gap_percent=0.1)
        unfilled_fvgs = [f for f in fvgs if not f["filled"]]
        bullish_fvgs = [f for f in unfilled_fvgs if f["type"] == "bullish"]
        bearish_fvgs = [f for f in unfilled_fvgs if f["type"] == "bearish"]
        
        # 4. Находим Order Blocks
        order_blocks = find_order_blocks(opens, highs, lows, closes, volumes)
        bullish_obs = [ob for ob in order_blocks if ob["type"] == "bullish"]
        bearish_obs = [ob for ob in order_blocks if ob["type"] == "bearish"]
        
        # 5. Находим зоны ликвидности
        liquidity = find_liquidity_zones(swing_highs, swing_lows, current_price)
        
        # 6. Определяем ближайшие уровни
        nearest_bullish_ob = min(bullish_obs, key=lambda x: abs(x["high"] - current_price)) if bullish_obs else None
        nearest_bearish_ob = min(bearish_obs, key=lambda x: abs(x["low"] - current_price)) if bearish_obs else None
        nearest_bullish_fvg = min(bullish_fvgs, key=lambda x: abs(x["top"] - current_price)) if bullish_fvgs else None
        nearest_bearish_fvg = min(bearish_fvgs, key=lambda x: abs(x["bottom"] - current_price)) if bearish_fvgs else None
        
        # 7. Формируем общий SMC сигнал
        bullish_signals = 0
        bearish_signals = 0
        
        if structure["trend"] == "bullish":
            bullish_signals += 2
        elif structure["trend"] == "bearish":
            bearish_signals += 2
        
        if len(bullish_fvgs) > len(bearish_fvgs):
            bullish_signals += 1
        elif len(bearish_fvgs) > len(bullish_fvgs):
            bearish_signals += 1
        
        if len(bullish_obs) > len(bearish_obs):
            bullish_signals += 1
        elif len(bearish_obs) > len(bullish_obs):
            bearish_signals += 1
        
        if bullish_signals > bearish_signals + 1:
            overall = "bullish"
            overall_emoji = "🟢"
        elif bearish_signals > bullish_signals + 1:
            overall = "bearish"
            overall_emoji = "🔴"
        else:
            overall = "neutral"
            overall_emoji = "⚪"
        
        return {
            "success": True,
            "symbol": klines_data["symbol"],
            "interval": interval,
            "current_price": round(current_price, 2),
            "structure": structure,
            "fair_value_gaps": {
                "total": len(fvgs),
                "unfilled": len(unfilled_fvgs),
                "bullish": len(bullish_fvgs),
                "bearish": len(bearish_fvgs),
                "recent": unfilled_fvgs[-5:] if unfilled_fvgs else [],
            },
            "order_blocks": {
                "total": len(order_blocks),
                "bullish": len(bullish_obs),
                "bearish": len(bearish_obs),
                "recent": order_blocks[-5:] if order_blocks else [],
            },
            "liquidity_zones": liquidity,
            "nearest_levels": {
                "bullish_ob": {"high": nearest_bullish_ob["high"], "low": nearest_bullish_ob["low"]} if nearest_bullish_ob else None,
                "bearish_ob": {"high": nearest_bearish_ob["high"], "low": nearest_bearish_ob["low"]} if nearest_bearish_ob else None,
                "bullish_fvg": {"top": nearest_bullish_fvg["top"], "bottom": nearest_bullish_fvg["bottom"]} if nearest_bullish_fvg else None,
                "bearish_fvg": {"top": nearest_bearish_fvg["top"], "bottom": nearest_bearish_fvg["bottom"]} if nearest_bearish_fvg else None,
            },
            "swing_points": {
                "highs": [{"price": h["price"]} for h in swing_highs[-5:]],
                "lows": [{"price": l["price"]} for l in swing_lows[-5:]],
            },
            "overall_signal": overall,
            "overall_emoji": overall_emoji,
            "summary": f"{overall_emoji} SMC: {overall}, {structure['trend_emoji']} Structure: {structure['structure']}, FVG: {len(unfilled_fvgs)}, OB: {len(order_blocks)}"
        }
    except Exception as e:
        logger.error(f"Error in SMC analysis for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class SmartMoneyTool(BaseTool):
    """
    Инструмент для Smart Money Concepts анализа.
    """
    
    name = "analyze_smart_money"
    description = "Smart Money анализ: FVG (имбалансы), Order Blocks, структура рынка (HH/HL/LL/LH), зоны ликвидности."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "interval": {"type": "string", "description": "Таймфрейм (1h, 4h, 1d)", "default": "1h"},
        "limit": {"type": "integer", "description": "Количество свечей", "default": 100}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, interval: str = "1h", limit: int = 100, **kwargs) -> ToolResult:
        result = analyze_smart_money(symbol, interval, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)