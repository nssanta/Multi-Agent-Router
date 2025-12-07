"""
Funding Rate & Open Interest Tool - данные с Binance Futures (бесплатный API)
"""

import logging
import requests
from typing import Dict, Any, List
from datetime import datetime
from backend.tools.base import BaseTool, ToolResult, register_tool

logger = logging.getLogger(__name__)

BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"


def get_funding_rate(symbol: str) -> Dict[str, Any]:
    """
    Получаем текущую ставку финансирования для указанного символа.
    :param symbol: Торговая пара
    :return: Словарь с данными о ставке финансирования
    """
    try:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Запрашиваем текущую ставку финансирования через API
        response = requests.get(
            f"{BINANCE_FAPI_BASE_URL}/fapi/v1/premiumIndex",
            params={"symbol": symbol},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        funding_rate = float(data.get("lastFundingRate", 0))
        funding_rate_percent = funding_rate * 100
        
        # Определяем настроение рынка на основе ставки финансирования
        if funding_rate_percent > 0.05:
            sentiment = "very_bullish"
            emoji = "🟢🟢"
        elif funding_rate_percent > 0.01:
            sentiment = "bullish"
            emoji = "🟢"
        elif funding_rate_percent < -0.05:
            sentiment = "very_bearish"
            emoji = "🔴🔴"
        elif funding_rate_percent < -0.01:
            sentiment = "bearish"
            emoji = "🔴"
        else:
            sentiment = "neutral"
            emoji = "⚪"
        
        # Получаем время следующего финансирования
        next_funding_time = int(data.get("nextFundingTime", 0))
        
        return {
            "success": True,
            "symbol": symbol,
            "funding_rate": funding_rate,
            "funding_rate_percent": round(funding_rate_percent, 4),
            "mark_price": float(data.get("markPrice", 0)),
            "index_price": float(data.get("indexPrice", 0)),
            "next_funding_time": datetime.fromtimestamp(next_funding_time / 1000).isoformat() if next_funding_time else None,
            "sentiment": sentiment,
            "sentiment_emoji": emoji,
            "interpretation": "Положительный = лонги платят шортам (бычий рынок)" if funding_rate > 0 else "Отрицательный = шорты платят лонгам (медвежий рынок)"
        }
    except Exception as e:
        logger.error(f"Error getting funding rate for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


def get_open_interest(symbol: str) -> Dict[str, Any]:
    """
    Получаем данные об открытом интересе для символа.
    :param symbol: Торговая пара
    :return: Словарь с данными об открытом интересе
    """
    try:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Запрашиваем данные об открытом интересе
        response = requests.get(
            f"{BINANCE_FAPI_BASE_URL}/fapi/v1/openInterest",
            params={"symbol": symbol},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        open_interest = float(data.get("openInterest", 0))
        
        return {
            "success": True,
            "symbol": symbol,
            "open_interest": open_interest,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting open interest for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


def get_open_interest_history(symbol: str, period: str = "1h", limit: int = 30) -> Dict[str, Any]:
    """
    Получаем историю открытого интереса.
    :param symbol: Торговая пара
    :param period: Временной период (например, "1h")
    :param limit: Лимит записей
    :return: Словарь с историческими данными открытого интереса
    """
    try:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Проверяем допустимость периода, иначе устанавливаем значение по умолчанию
        valid_periods = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
        if period not in valid_periods:
            period = "1h"
        
        # Запрашиваем историю открытого интереса
        response = requests.get(
            f"{BINANCE_FAPI_BASE_URL}/futures/data/openInterestHist",
            params={"symbol": symbol, "period": period, "limit": min(limit, 500)},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return {"success": False, "error": "No OI history data", "symbol": symbol}
        
        # Анализируем изменение открытого интереса
        oi_values = [float(d.get("sumOpenInterest", 0)) for d in data]
        first_oi = oi_values[0] if oi_values else 0
        last_oi = oi_values[-1] if oi_values else 0
        
        oi_change_percent = ((last_oi - first_oi) / first_oi * 100) if first_oi > 0 else 0
        
        # Определяем тренд открытого интереса
        if oi_change_percent > 10:
            oi_trend = "strong_increase"
            oi_emoji = "📈📈"
        elif oi_change_percent > 3:
            oi_trend = "increasing"
            oi_emoji = "📈"
        elif oi_change_percent < -10:
            oi_trend = "strong_decrease"
            oi_emoji = "📉📉"
        elif oi_change_percent < -3:
            oi_trend = "decreasing"
            oi_emoji = "📉"
        else:
            oi_trend = "stable"
            oi_emoji = "➡️"
        
        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "data_points": len(data),
            "first_oi": first_oi,
            "last_oi": last_oi,
            "oi_change_percent": round(oi_change_percent, 2),
            "oi_trend": oi_trend,
            "oi_emoji": oi_emoji,
            "max_oi": max(oi_values) if oi_values else 0,
            "min_oi": min(oi_values) if oi_values else 0,
        }
    except Exception as e:
        logger.error(f"Error getting OI history for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


def get_long_short_ratio(symbol: str, period: str = "1h") -> Dict[str, Any]:
    """
    Получаем соотношение позиций Long/Short.
    :param symbol: Торговая пара
    :param period: Временной период
    :return: Словарь с данными соотношения Long/Short
    """
    try:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Запрашиваем данные Top Trader Long/Short Ratio
        response = requests.get(
            f"{BINANCE_FAPI_BASE_URL}/futures/data/topLongShortPositionRatio",
            params={"symbol": symbol, "period": period, "limit": 1},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return {"success": False, "error": "No L/S ratio data", "symbol": symbol}
        
        latest = data[-1]
        long_ratio = float(latest.get("longAccount", 0.5)) * 100
        short_ratio = float(latest.get("shortAccount", 0.5)) * 100
        ls_ratio = float(latest.get("longShortRatio", 1))
        
        # Интерпретируем полученные данные
        if ls_ratio > 2:
            sentiment = "very_bullish"
            emoji = "🟢🟢"
        elif ls_ratio > 1.2:
            sentiment = "bullish"
            emoji = "🟢"
        elif ls_ratio < 0.5:
            sentiment = "very_bearish"
            emoji = "🔴🔴"
        elif ls_ratio < 0.8:
            sentiment = "bearish"
            emoji = "🔴"
        else:
            sentiment = "neutral"
            emoji = "⚪"
        
        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "long_percent": round(long_ratio, 2),
            "short_percent": round(short_ratio, 2),
            "long_short_ratio": round(ls_ratio, 3),
            "sentiment": sentiment,
            "sentiment_emoji": emoji,
            "timestamp": latest.get("timestamp"),
        }
    except Exception as e:
        logger.error(f"Error getting L/S ratio for {symbol}: {e}")
        return {"success": False, "error": str(e), "symbol": symbol}


def get_futures_market_data(symbol: str) -> Dict[str, Any]:
    """
    Получаем все фьючерсные данные одним вызовом.
    :param symbol: Торговая пара
    :return: Словарь с агрегированными фьючерсными данными
    """
    funding = get_funding_rate(symbol)
    oi = get_open_interest(symbol)
    oi_hist = get_open_interest_history(symbol, "1h", 24)
    ls_ratio = get_long_short_ratio(symbol, "1h")
    
    # Рассчитываем общий sentiment на основе всех данных
    bullish_signals = 0
    bearish_signals = 0
    
    if funding.get("success") and "bullish" in funding.get("sentiment", ""):
        bullish_signals += 1
    elif funding.get("success") and "bearish" in funding.get("sentiment", ""):
        bearish_signals += 1
    
    if ls_ratio.get("success") and "bullish" in ls_ratio.get("sentiment", ""):
        bullish_signals += 1
    elif ls_ratio.get("success") and "bearish" in ls_ratio.get("sentiment", ""):
        bearish_signals += 1
    
    if oi_hist.get("success") and "increase" in oi_hist.get("oi_trend", ""):
        bullish_signals += 0.5  # Рост OI может быть и бычьим и медвежьим
    
    if bullish_signals > bearish_signals + 0.5:
        overall_sentiment = "bullish"
        overall_emoji = "🟢"
    elif bearish_signals > bullish_signals + 0.5:
        overall_sentiment = "bearish"
        overall_emoji = "🔴"
    else:
        overall_sentiment = "neutral"
        overall_emoji = "⚪"
    
    return {
        "success": True,
        "symbol": symbol.upper(),
        "funding_rate": funding,
        "open_interest": oi,
        "oi_history": oi_hist,
        "long_short_ratio": ls_ratio,
        "overall_sentiment": overall_sentiment,
        "overall_emoji": overall_emoji,
        "summary": f"{overall_emoji} Futures: {overall_sentiment}, FR: {funding.get('funding_rate_percent', 0):.4f}%, L/S: {ls_ratio.get('long_short_ratio', 1):.2f}"
    }


@register_tool
class FundingRateTool(BaseTool):
    """
    Инструмент для получения Funding Rate с Binance Futures.
    """
    
    name = "get_funding_rate"
    description = "Получить ставку финансирования (Funding Rate) для фьючерсов."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара (BTC, ETH)"}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, **kwargs) -> ToolResult:
        result = get_funding_rate(symbol)
        if result["success"]:
            return ToolResult.success(data=result, message=f"FR: {result['funding_rate_percent']:.4f}% {result['sentiment_emoji']}")
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)


@register_tool
class FuturesMarketTool(BaseTool):
    """
    Инструмент для получения всех фьючерсных данных.
    """
    
    name = "get_futures_data"
    description = "Получить Funding Rate, Open Interest и Long/Short Ratio."
    
    parameters = {
        "symbol": {"type": "string", "description": "Торговая пара (BTC, ETH)"}
    }
    
    required_params = ["symbol"]
    agent_types = ["crypto"]
    
    def execute(self, symbol: str, **kwargs) -> ToolResult:
        result = get_futures_market_data(symbol)
        if result["success"]:
            return ToolResult.success(data=result, message=result.get("summary", ""))
        return ToolResult.error(error=result.get("error", "Unknown error"), data=result)