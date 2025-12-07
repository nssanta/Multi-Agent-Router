"""
Multi-Timeframe Analysis Tool - анализ на трёх горизонтах

Горизонты:
- Краткосрок: 1m, 3m, 5m, 15m (scalping/intraday)
- Среднесрок: 1h, 4h, 8h, 1d (swing trading)
- Долгосрок: 1d, 3d, 1w, 1M (position trading)
"""

import logging
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.tools.base import BaseTool, ToolResult, register_tool
from .klines_tool import get_klines
from .indicators_tool import calculate_indicators

logger = logging.getLogger(__name__)

# Определение горизонтов
TIMEFRAME_HORIZONS = {
    "short": {
        "name": "Краткосрок",
        "name_en": "Short-term",
        "timeframes": ["3m", "5m", "15m"],
        "emoji": "⚡",
        "description": "Scalping/Intraday (1-30 мин)"
    },
    "medium": {
        "name": "Среднесрок",
        "name_en": "Medium-term",
        "timeframes": ["1h", "4h", "1d"],
        "emoji": "📊",
        "description": "Swing trading (1ч - 24ч)"
    },
    "long": {
        "name": "Долгосрок",
        "name_en": "Long-term",
        "timeframes": ["1d", "1w", "1M"],
        "emoji": "🎯",
        "description": "Position trading (1-3 месяца)"
    }
}


def analyze_single_timeframe(symbol: str, interval: str, limit: int = 100) -> Dict[str, Any]:
    """
    Анализируем данные для одного таймфрейма.
    :param symbol: Торговая пара
    :param interval: Интервал (таймфрейм)
    :param limit: Лимит свечей
    :return: Результаты анализа таймфрейма
    """
    try:
        klines = get_klines(symbol, interval, limit)
        if not klines["success"]:
            return {"success": False, "interval": interval, "error": klines.get("error")}
        
        indicators = calculate_indicators(klines["ohlcv"])
        if not indicators["success"]:
            return {"success": False, "interval": interval, "error": indicators.get("error")}
        
        return {
            "success": True,
            "interval": interval,
            "current_price": klines["current_price"],
            "overall_signal": indicators["overall_signal"],
            "bullish_count": indicators["bullish_count"],
            "bearish_count": indicators["bearish_count"],
            "total_indicators": indicators.get("total_indicators", 0),
            "key_indicators": {
                "rsi": indicators["indicators"].get("rsi", {}),
                "macd": indicators["indicators"].get("macd", {}),
                "supertrend": indicators["indicators"].get("supertrend", {}),
            }
        }
    except Exception as e:
        logger.error(f"Error analyzing {interval}: {e}")
        return {"success": False, "interval": interval, "error": str(e)}


def analyze_horizon(symbol: str, horizon: str) -> Dict[str, Any]:
    """
    Анализируем один горизонт (параллельно по таймфреймам).
    :param symbol: Торговая пара
    :param horizon: Горизонт (short/medium/long)
    :return: Результаты анализа горизонта
    """
    if horizon not in TIMEFRAME_HORIZONS:
        return {"success": False, "error": f"Unknown horizon: {horizon}"}
    
    config = TIMEFRAME_HORIZONS[horizon]
    timeframes = config["timeframes"]
    
    results = {}
    bullish_tfs = 0
    bearish_tfs = 0
    
    # Запускаем параллельный анализ таймфреймов
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(analyze_single_timeframe, symbol, tf): tf 
            for tf in timeframes
        }
        
        for future in as_completed(futures):
            tf = futures[future]
            try:
                result = future.result()
                results[tf] = result
                
                if result.get("success"):
                    signal = result.get("overall_signal", "neutral")
                    if "bullish" in signal:
                        bullish_tfs += 1
                    elif "bearish" in signal:
                        bearish_tfs += 1
            except Exception as e:
                logger.error(f"Error in {tf}: {e}")
                results[tf] = {"success": False, "error": str(e)}
    
    # Определяем общий сигнал горизонта
    if bullish_tfs >= 2:
        horizon_signal = "bullish"
        horizon_emoji = "🟢"
    elif bearish_tfs >= 2:
        horizon_signal = "bearish"
        horizon_emoji = "🔴"
    else:
        horizon_signal = "neutral"
        horizon_emoji = "⚪"
    
    return {
        "success": True,
        "horizon": horizon,
        "name": config["name"],
        "emoji": config["emoji"],
        "description": config["description"],
        "timeframes": results,
        "bullish_timeframes": bullish_tfs,
        "bearish_timeframes": bearish_tfs,
        "horizon_signal": horizon_signal,
        "horizon_emoji": horizon_emoji,
    }


def run_mtf_analysis(symbol: str, horizons: List[str] = None) -> Dict[str, Any]:
    """
    Выполняем полный мульти-таймфрейм анализ.
    :param symbol: Торговая пара
    :param horizons: Список горизонтов
    :return: Результаты полного анализа
    """
    if horizons is None:
        horizons = ["short", "medium", "long"]
    
    try:
        results = {}
        overall_bullish = 0
        overall_bearish = 0
        
        # Анализируем каждый горизонт
        for horizon in horizons:
            horizon_result = analyze_horizon(symbol, horizon)
            results[horizon] = horizon_result
            
            if horizon_result.get("success"):
                signal = horizon_result.get("horizon_signal", "neutral")
                if signal == "bullish":
                    overall_bullish += 1
                elif signal == "bearish":
                    overall_bearish += 1
        
        # Определяем общий MTF сигнал
        if overall_bullish >= 2:
            mtf_signal = "strong_bullish"
            mtf_emoji = "🟢🟢"
        elif overall_bullish > overall_bearish:
            mtf_signal = "bullish"
            mtf_emoji = "🟢"
        elif overall_bearish >= 2:
            mtf_signal = "strong_bearish"
            mtf_emoji = "🔴🔴"
        elif overall_bearish > overall_bullish:
            mtf_signal = "bearish"
            mtf_emoji = "🔴"
        else:
            mtf_signal = "neutral"
            mtf_emoji = "⚪"
        
        # Определяем консенсус
        if overall_bullish == 3:
            consensus = "full_bullish"
            consensus_text = "Все горизонты бычьи 🎯"
        elif overall_bearish == 3:
            consensus = "full_bearish"
            consensus_text = "Все горизонты медвежьи ⚠️"
        elif overall_bullish == 0 and overall_bearish == 0:
            consensus = "all_neutral"
            consensus_text = "Все горизонты нейтральны"
        else:
            consensus = "mixed"
            consensus_text = "Смешанные сигналы"
        
        # Формируем summary по каждому горизонту
        horizon_summaries = []
        for h in horizons:
            if results.get(h, {}).get("success"):
                emoji = results[h]["horizon_emoji"]
                name = results[h]["name"]
                signal = results[h]["horizon_signal"]
                horizon_summaries.append(f"{emoji} {name}: {signal}")
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "horizons": results,
            "mtf_signal": mtf_signal,
            "mtf_emoji": mtf_emoji,
            "bullish_horizons": overall_bullish,
            "bearish_horizons": overall_bearish,
            "consensus": consensus,
            "consensus_text": consensus_text,
            "summary": f"{mtf_emoji} MTF: {mtf_signal} | " + " | ".join(horizon_summaries)
        }
    except Exception as e:
        logger.error(f"Error in MTF analysis for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


@register_tool
class MTFAnalysisTool(BaseTool):
    """
    Инструмент для мульти-таймфрейм анализа.
    """
    
    name = "analyze_mtf"
    description = "Мульти-таймфрейм анализ на трёх горизонтах: краткосрок (3m/5m/15m), среднесрок (1h/4h/1d), долгосрок (1d/1w/1M)."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара"},
        "horizons": {"type": "array", "description": "Горизонты (short/medium/long)", "default": ["short", "medium", "long"]}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, horizons: List[str] = None, **kwargs) -> ToolResult:
        result = run_mtf_analysis(symbol, horizons)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)