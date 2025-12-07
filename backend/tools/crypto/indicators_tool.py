"""
Indicators Tool - расчёт технических индикаторов (12 индикаторов)
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


# Список всех поддерживаемых индикаторов
ALL_INDICATORS = [
    "rsi", "macd", "ema", "bollinger", "stoch_rsi", 
    "adx", "atr", "vwap", "obv", "ichimoku", "supertrend", "cmf"
]


def calculate_indicators(ohlcv_data: Dict[str, List], indicators: List[str] = None) -> Dict[str, Any]:
    """
    Рассчитываем технические индикаторы (12 штук).
    :param ohlcv_data: Данные OHLCV
    :param indicators: Список запрашиваемых индикаторов
    :return: Результаты расчета индикаторов
    """
    if not PANDAS_TA_AVAILABLE:
        return {"success": False, "error": "pandas-ta not installed"}
    
    if indicators is None:
        indicators = ALL_INDICATORS
    
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
        
        # 1. Рассчитываем RSI (Relative Strength Index)
        if "rsi" in indicators:
            try:
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
            except Exception as e:
                logger.debug(f"RSI error: {e}")
        
        # 2. Рассчитываем MACD (Moving Average Convergence Divergence)
        if "macd" in indicators:
            try:
                macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
                if macd is not None and len(macd) > 0:
                    macd_line = macd.iloc[-1, 0]
                    signal_line = macd.iloc[-1, 1]
                    histogram = macd.iloc[-1, 2] if len(macd.columns) > 2 else 0
                    signal = "bullish" if macd_line > signal_line else "bearish"
                    if signal == "bullish":
                        bullish_count += 1
                    else:
                        bearish_count += 1
                    results["indicators"]["macd"] = {
                        "macd": round(macd_line, 4),
                        "signal": round(signal_line, 4),
                        "histogram": round(histogram, 4),
                        "trend": signal
                    }
            except Exception as e:
                logger.debug(f"MACD error: {e}")
        
        # 3. Рассчитываем EMA (Exponential Moving Average)
        if "ema" in indicators:
            try:
                ema_9 = ta.ema(df["close"], length=9)
                ema_21 = ta.ema(df["close"], length=21)
                ema_50 = ta.ema(df["close"], length=50)
                current_price = df["close"].iloc[-1]
                
                if ema_9 is not None and ema_21 is not None:
                    ema_9_val = ema_9.iloc[-1]
                    ema_21_val = ema_21.iloc[-1]
                    ema_50_val = ema_50.iloc[-1] if ema_50 is not None and len(ema_50) > 0 else None
                    
                    # Определяем тренд по расположению EMA
                    if ema_9_val > ema_21_val and current_price > ema_9_val:
                        trend = "bullish"
                        bullish_count += 1
                    elif ema_9_val < ema_21_val and current_price < ema_9_val:
                        trend = "bearish"
                        bearish_count += 1
                    else:
                        trend = "neutral"
                    
                    results["indicators"]["ema"] = {
                        "ema_9": round(ema_9_val, 2),
                        "ema_21": round(ema_21_val, 2),
                        "ema_50": round(ema_50_val, 2) if ema_50_val else None,
                        "trend": trend
                    }
            except Exception as e:
                logger.debug(f"EMA error: {e}")
        
        # 4. Рассчитываем Bollinger Bands
        if "bollinger" in indicators:
            try:
                bbands = ta.bbands(df["close"], length=20, std=2)
                if bbands is not None and len(bbands) > 0:
                    current_price = df["close"].iloc[-1]
                    upper = bbands.iloc[-1, 0]
                    mid = bbands.iloc[-1, 1]
                    lower = bbands.iloc[-1, 2]
                    
                    # Определяем позицию цены относительно полос
                    band_width = (upper - lower) / mid * 100
                    position = (current_price - lower) / (upper - lower) if upper != lower else 0.5
                    
                    if position < 0.2:
                        signal = "oversold"
                        bullish_count += 1
                    elif position > 0.8:
                        signal = "overbought"
                        bearish_count += 1
                    else:
                        signal = "neutral"
                    
                    results["indicators"]["bollinger"] = {
                        "upper": round(upper, 2),
                        "middle": round(mid, 2),
                        "lower": round(lower, 2),
                        "bandwidth": round(band_width, 2),
                        "position": round(position, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"Bollinger error: {e}")
        
        # 5. Рассчитываем Stochastic RSI
        if "stoch_rsi" in indicators:
            try:
                stoch_rsi = ta.stochrsi(df["close"], length=14)
                if stoch_rsi is not None and len(stoch_rsi) > 0:
                    k = stoch_rsi.iloc[-1, 0]
                    d = stoch_rsi.iloc[-1, 1]
                    
                    if k < 20:
                        signal = "oversold"
                        bullish_count += 1
                    elif k > 80:
                        signal = "overbought"
                        bearish_count += 1
                    else:
                        signal = "neutral"
                    
                    results["indicators"]["stoch_rsi"] = {
                        "k": round(k, 2),
                        "d": round(d, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"Stoch RSI error: {e}")
        
        # 6. Рассчитываем ADX (Average Directional Index)
        if "adx" in indicators:
            try:
                adx = ta.adx(df["high"], df["low"], df["close"], length=14)
                if adx is not None and len(adx) > 0:
                    adx_val = adx.iloc[-1, 0]
                    plus_di = adx.iloc[-1, 1]
                    minus_di = adx.iloc[-1, 2]
                    
                    # Если ADX > 25, считаем тренд сильным
                    trend_strength = "strong" if adx_val > 25 else "weak"
                    trend_direction = "bullish" if plus_di > minus_di else "bearish"
                    
                    if adx_val > 25:
                        if plus_di > minus_di:
                            bullish_count += 1
                        else:
                            bearish_count += 1
                    
                    results["indicators"]["adx"] = {
                        "adx": round(adx_val, 2),
                        "plus_di": round(plus_di, 2),
                        "minus_di": round(minus_di, 2),
                        "trend_strength": trend_strength,
                        "trend_direction": trend_direction
                    }
            except Exception as e:
                logger.debug(f"ADX error: {e}")
        
        # 7. Рассчитываем ATR (Average True Range)
        if "atr" in indicators:
            try:
                atr = ta.atr(df["high"], df["low"], df["close"], length=14)
                if atr is not None and len(atr) > 0:
                    atr_val = atr.iloc[-1]
                    current_price = df["close"].iloc[-1]
                    atr_percent = (atr_val / current_price) * 100
                    
                    # Определяем уровень волатильности
                    volatility = "high" if atr_percent > 3 else "low" if atr_percent < 1 else "medium"
                    
                    results["indicators"]["atr"] = {
                        "atr": round(atr_val, 4),
                        "atr_percent": round(atr_percent, 2),
                        "volatility": volatility
                    }
            except Exception as e:
                logger.debug(f"ATR error: {e}")
        
        # 8. Рассчитываем VWAP (Volume Weighted Average Price) вручную
        if "vwap" in indicators:
            try:
                # Используем ручной расчёт, так как pandas-ta иногда требует DatetimeIndex
                typical_price = (df["high"] + df["low"] + df["close"]) / 3
                cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
                cumulative_vol = df["volume"].cumsum()
                vwap_series = cumulative_tp_vol / cumulative_vol
                
                if len(vwap_series) > 0:
                    vwap_val = vwap_series.iloc[-1]
                    current_price = df["close"].iloc[-1]
                    
                    if current_price > vwap_val * 1.01:
                        signal = "above_vwap"
                        bullish_count += 1
                    elif current_price < vwap_val * 0.99:
                        signal = "below_vwap"
                        bearish_count += 1
                    else:
                        signal = "at_vwap"
                    
                    results["indicators"]["vwap"] = {
                        "vwap": round(vwap_val, 2),
                        "deviation": round((current_price - vwap_val) / vwap_val * 100, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"VWAP error: {e}")
        
        # 9. Рассчитываем OBV (On-Balance Volume)
        if "obv" in indicators:
            try:
                obv = ta.obv(df["close"], df["volume"])
                if obv is not None and len(obv) > 5:
                    current_obv = obv.iloc[-1]
                    prev_obv = obv.iloc[-5]  # 5 периодов назад
                    
                    obv_change = ((current_obv - prev_obv) / abs(prev_obv)) * 100 if prev_obv != 0 else 0
                    
                    if obv_change > 5:
                        signal = "accumulation"
                        bullish_count += 1
                    elif obv_change < -5:
                        signal = "distribution"
                        bearish_count += 1
                    else:
                        signal = "neutral"
                    
                    results["indicators"]["obv"] = {
                        "obv": round(current_obv, 0),
                        "change_5p": round(obv_change, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"OBV error: {e}")
        
        # 10. Рассчитываем Ichimoku Cloud
        if "ichimoku" in indicators:
            try:
                ichimoku = ta.ichimoku(df["high"], df["low"], df["close"])
                if ichimoku is not None and len(ichimoku[0]) > 0:
                    span_a = ichimoku[0].iloc[-1, 0]  # Senkou Span A
                    span_b = ichimoku[0].iloc[-1, 1]  # Senkou Span B
                    tenkan = ichimoku[0].iloc[-1, 2] if len(ichimoku[0].columns) > 2 else None
                    kijun = ichimoku[0].iloc[-1, 3] if len(ichimoku[0].columns) > 3 else None
                    current_price = df["close"].iloc[-1]
                    
                    # Цена выше облака = бычий сигнал, ниже = медвежий
                    cloud_top = max(span_a, span_b)
                    cloud_bottom = min(span_a, span_b)
                    
                    if current_price > cloud_top:
                        signal = "above_cloud"
                        bullish_count += 1
                    elif current_price < cloud_bottom:
                        signal = "below_cloud"
                        bearish_count += 1
                    else:
                        signal = "in_cloud"
                    
                    results["indicators"]["ichimoku"] = {
                        "senkou_a": round(span_a, 2),
                        "senkou_b": round(span_b, 2),
                        "cloud_top": round(cloud_top, 2),
                        "cloud_bottom": round(cloud_bottom, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"Ichimoku error: {e}")
        
        # 11. Рассчитываем SuperTrend
        if "supertrend" in indicators:
            try:
                supertrend = ta.supertrend(df["high"], df["low"], df["close"], length=10, multiplier=3)
                if supertrend is not None and len(supertrend) > 0:
                    st_value = supertrend.iloc[-1, 0]
                    st_direction = supertrend.iloc[-1, 1]  # 1 = bullish, -1 = bearish
                    current_price = df["close"].iloc[-1]
                    
                    if st_direction == 1 or current_price > st_value:
                        signal = "bullish"
                        bullish_count += 1
                    else:
                        signal = "bearish"
                        bearish_count += 1
                    
                    results["indicators"]["supertrend"] = {
                        "value": round(st_value, 2),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"SuperTrend error: {e}")
        
        # 12. Рассчитываем CMF (Chaikin Money Flow)
        if "cmf" in indicators:
            try:
                cmf = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20)
                if cmf is not None and len(cmf) > 0:
                    cmf_val = cmf.iloc[-1]
                    
                    if cmf_val > 0.1:
                        signal = "strong_buying"
                        bullish_count += 1
                    elif cmf_val > 0:
                        signal = "buying"
                    elif cmf_val < -0.1:
                        signal = "strong_selling"
                        bearish_count += 1
                    else:
                        signal = "selling"
                    
                    results["indicators"]["cmf"] = {
                        "value": round(cmf_val, 4),
                        "signal": signal
                    }
            except Exception as e:
                logger.debug(f"CMF error: {e}")
        
        # Определяем общий сигнал на основе всех индикаторов
        total_signals = bullish_count + bearish_count
        if total_signals > 0:
            bullish_ratio = bullish_count / total_signals
            if bullish_ratio > 0.65:
                results["overall_signal"] = "strong_bullish"
            elif bullish_ratio > 0.55:
                results["overall_signal"] = "bullish"
            elif bullish_ratio < 0.35:
                results["overall_signal"] = "strong_bearish"
            elif bullish_ratio < 0.45:
                results["overall_signal"] = "bearish"
            else:
                results["overall_signal"] = "neutral"
        
        results["bullish_count"] = bullish_count
        results["bearish_count"] = bearish_count
        results["total_indicators"] = len(results["indicators"])
        
        return results
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return {"success": False, "error": str(e)}


@register_tool
class IndicatorsTool(BaseTool):
    """
    Инструмент для расчёта технических индикаторов (12 индикаторов).
    """
    
    name = "calculate_indicators"
    description = "Рассчитать технические индикаторы (RSI, MACD, EMA, Bollinger, StochRSI, ADX, ATR, VWAP, OBV, Ichimoku, SuperTrend, CMF)."
    
    parameters = {
        "ohlcv_data": {"type": "object", "description": "OHLCV данные"},
        "indicators": {"type": "array", "description": "Список индикаторов (опционально, по умолчанию все 12)"}
    }
    
    required_params = ["ohlcv_data"]
    agent_types = ["crypto"]
    
    def execute(self, ohlcv_data: Dict[str, List], indicators: List[str] = None, **kwargs) -> ToolResult:
        result = calculate_indicators(ohlcv_data, indicators)
        if result["success"]:
            signal = result.get('overall_signal', 'neutral')
            count = result.get('total_indicators', 0)
            return ToolResult.success(data=result, message=f"Signal: {signal} ({count} indicators)")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)