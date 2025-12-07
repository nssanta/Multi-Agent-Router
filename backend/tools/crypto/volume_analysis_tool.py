"""
Volume Analysis Tool - анализ объёмов

Включает:
- Volume Delta
- Relative Volume
- Volume Profile (по ценовым уровням)
- Volume Trend
"""

import logging
from typing import Dict, Any, List
from backend.tools.base import BaseTool, ToolResult, register_tool
from .klines_tool import get_klines

logger = logging.getLogger(__name__)


def calculate_volume_delta(ohlcv: Dict[str, List]) -> Dict[str, Any]:
    """
    Рассчитываем Volume Delta (разница между buy и sell volume).
    :param ohlcv: Словарь с данными OHLCV
    :return: Словарь с результатами расчета дельты объема
    """
    opens = ohlcv["open"]
    closes = ohlcv["close"]
    volumes = ohlcv["volume"]
    
    # Используем приближение: если close > open = buy volume, иначе sell
    buy_volume = 0
    sell_volume = 0
    
    for i in range(len(volumes)):
        if closes[i] >= opens[i]:
            buy_volume += volumes[i]
        else:
            sell_volume += volumes[i]
    
    total_volume = buy_volume + sell_volume
    delta = buy_volume - sell_volume
    delta_percent = (delta / total_volume * 100) if total_volume > 0 else 0
    
    if delta_percent > 20:
        signal = "strong_buying"
        emoji = "🟢🟢"
    elif delta_percent > 5:
        signal = "buying"
        emoji = "🟢"
    elif delta_percent < -20:
        signal = "strong_selling"
        emoji = "🔴🔴"
    elif delta_percent < -5:
        signal = "selling"
        emoji = "🔴"
    else:
        signal = "neutral"
        emoji = "⚪"
    
    return {
        "buy_volume": round(buy_volume, 2),
        "sell_volume": round(sell_volume, 2),
        "total_volume": round(total_volume, 2),
        "delta": round(delta, 2),
        "delta_percent": round(delta_percent, 2),
        "signal": signal,
        "emoji": emoji,
    }


def calculate_relative_volume(volumes: List[float], period: int = 20) -> Dict[str, Any]:
    """
    Рассчитываем Relative Volume (текущий объем против среднего).
    :param volumes: Список объемов
    :param period: Период усреднения
    :return: Словарь с результатами расчета относительного объема
    """
    if len(volumes) < period + 1:
        return {"rvol": 1.0, "signal": "normal", "emoji": "➡️"}
    
    current_volume = volumes[-1]
    avg_volume = sum(volumes[-period-1:-1]) / period
    
    rvol = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    if rvol > 3:
        signal = "extreme"
        emoji = "🔥🔥"
    elif rvol > 2:
        signal = "very_high"
        emoji = "🔥"
    elif rvol > 1.5:
        signal = "high"
        emoji = "📈"
    elif rvol < 0.5:
        signal = "very_low"
        emoji = "💤"
    elif rvol < 0.75:
        signal = "low"
        emoji = "📉"
    else:
        signal = "normal"
        emoji = "➡️"
    
    return {
        "current_volume": round(current_volume, 2),
        "avg_volume": round(avg_volume, 2),
        "rvol": round(rvol, 2),
        "signal": signal,
        "emoji": emoji,
    }


def calculate_volume_profile(ohlcv: Dict[str, List], num_levels: int = 10) -> Dict[str, Any]:
    """
    Рассчитываем Volume Profile (распределение объема по ценовым уровням).
    :param ohlcv: Словарь с данными OHLCV
    :param num_levels: Количество ценовых уровней
    :return: Словарь с профилем объема
    """
    highs = ohlcv["high"]
    lows = ohlcv["low"]
    closes = ohlcv["close"]
    volumes = ohlcv["volume"]
    
    # Определяем диапазон цен
    price_min = min(lows)
    price_max = max(highs)
    price_range = price_max - price_min
    
    if price_range == 0:
        return {"levels": [], "poc": 0, "vah": 0, "val": 0}
    
    level_size = price_range / num_levels
    
    # Распределяем объём по уровням
    levels = []
    for i in range(num_levels):
        level_low = price_min + i * level_size
        level_high = level_low + level_size
        level_mid = (level_low + level_high) / 2
        
        # Суммируем объём свечей, которые попадают в этот уровень
        level_volume = 0
        for j in range(len(closes)):
            candle_mid = (highs[j] + lows[j]) / 2
            if level_low <= candle_mid <= level_high:
                level_volume += volumes[j]
        
        levels.append({
            "price_low": round(level_low, 2),
            "price_high": round(level_high, 2),
            "price_mid": round(level_mid, 2),
            "volume": round(level_volume, 2),
        })
    
    # Находим Point of Control (POC) - уровень с максимальным объёмом
    poc_level = max(levels, key=lambda x: x["volume"])
    
    # Рассчитываем Value Area (70% объёма)
    total_vol = sum(l["volume"] for l in levels)
    sorted_levels = sorted(levels, key=lambda x: x["volume"], reverse=True)
    
    cumulative = 0
    value_area_levels = []
    for level in sorted_levels:
        cumulative += level["volume"]
        value_area_levels.append(level)
        if cumulative >= total_vol * 0.7:
            break
    
    vah = max(l["price_high"] for l in value_area_levels) if value_area_levels else price_max
    val = min(l["price_low"] for l in value_area_levels) if value_area_levels else price_min
    
    return {
        "levels": sorted(levels, key=lambda x: x["price_mid"]),
        "poc": round(poc_level["price_mid"], 2),
        "poc_volume": round(poc_level["volume"], 2),
        "vah": round(vah, 2),  # Value Area High
        "val": round(val, 2),  # Value Area Low
        "total_volume": round(total_vol, 2),
    }


def calculate_volume_trend(volumes: List[float], period: int = 10) -> Dict[str, Any]:
    """
    Анализируем тренд объёма.
    :param volumes: Список объемов
    :param period: Период анализа
    :return: Словарь с трендом объема
    """
    if len(volumes) < period * 2:
        return {"trend": "unknown", "emoji": "❓"}
    
    recent_avg = sum(volumes[-period:]) / period
    previous_avg = sum(volumes[-period*2:-period]) / period
    
    change_percent = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
    
    if change_percent > 50:
        trend = "strong_increasing"
        emoji = "📈📈"
    elif change_percent > 20:
        trend = "increasing"
        emoji = "📈"
    elif change_percent < -50:
        trend = "strong_decreasing"
        emoji = "📉📉"
    elif change_percent < -20:
        trend = "decreasing"
        emoji = "📉"
    else:
        trend = "stable"
        emoji = "➡️"
    
    return {
        "recent_avg": round(recent_avg, 2),
        "previous_avg": round(previous_avg, 2),
        "change_percent": round(change_percent, 2),
        "trend": trend,
        "emoji": emoji,
    }


def analyze_volume(symbol: str, interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
    """
    Выполняем полный анализ объёмов.
    :param symbol: Торговая пара
    :param interval: Интервал
    :param limit: Лимит свечей
    :return: Результаты полного анализа объемов
    """
    klines_data = get_klines(symbol, interval, limit)
    
    if not klines_data["success"]:
        return klines_data
    
    try:
        ohlcv = klines_data["ohlcv"]
        volumes = ohlcv["volume"]
        current_price = ohlcv["close"][-1] if ohlcv["close"] else 0
        
        # 1. Рассчитываем Volume Delta
        delta = calculate_volume_delta(ohlcv)
        
        # 2. Рассчитываем Relative Volume
        rvol = calculate_relative_volume(volumes)
        
        # 3. Рассчитываем Volume Profile
        profile = calculate_volume_profile(ohlcv)
        
        # 4. Анализируем Volume Trend
        trend = calculate_volume_trend(volumes)
        
        # 5. Определяем общий сигнал
        bullish_signals = 0
        bearish_signals = 0
        
        if "buying" in delta["signal"]:
            bullish_signals += 1
        elif "selling" in delta["signal"]:
            bearish_signals += 1
        
        if trend["trend"] in ["increasing", "strong_increasing"]:
            bullish_signals += 0.5  # Рост объёма может быть и бычьим и медвежьим
        
        # Анализируем позицию цены относительно POC
        if current_price > profile.get("poc", 0):
            bullish_signals += 0.5
        else:
            bearish_signals += 0.5
        
        if bullish_signals > bearish_signals + 0.5:
            overall = "bullish"
            overall_emoji = "🟢"
        elif bearish_signals > bullish_signals + 0.5:
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
            "volume_delta": delta,
            "relative_volume": rvol,
            "volume_profile": profile,
            "volume_trend": trend,
            "overall_signal": overall,
            "overall_emoji": overall_emoji,
            "summary": f"{overall_emoji} Volume: {overall}, {delta['emoji']} Delta: {delta['delta_percent']:.1f}%, {rvol['emoji']} RVol: {rvol['rvol']:.2f}x, {trend['emoji']} Trend: {trend['trend']}"
        }
    except Exception as e:
        logger.error(f"Error in volume analysis for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class VolumeAnalysisTool(BaseTool):
    """
    Инструмент для анализа объёмов.
    """
    
    name = "analyze_volume"
    description = "Анализ объёмов: Volume Delta, Relative Volume, Volume Profile, Volume Trend."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "interval": {"type": "string", "description": "Таймфрейм", "default": "1h"},
        "limit": {"type": "integer", "description": "Количество свечей", "default": 100}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, interval: str = "1h", limit: int = 100, **kwargs) -> ToolResult:
        result = analyze_volume(symbol, interval, limit)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)