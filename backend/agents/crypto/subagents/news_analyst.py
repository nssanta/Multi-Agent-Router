"""
News Analyst - анализ новостей (Fear & Greed, CoinGecko)
"""

import logging
import requests
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def get_fear_greed_index() -> Dict[str, Any]:
    """Получить Fear & Greed Index"""
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [{}])[0]
        
        value = int(data.get("value", 50))
        classification = data.get("value_classification", "Neutral")
        
        if value <= 25:
            emoji = "😱"
        elif value <= 45:
            emoji = "😨"
        elif value <= 55:
            emoji = "😐"
        elif value <= 75:
            emoji = "😊"
        else:
            emoji = "🤑"
        
        return {"success": True, "value": value, "classification": classification, "emoji": emoji}
    except Exception as e:
        logger.error(f"Fear & Greed error: {e}")
        return {"success": False, "value": 50, "classification": "Unknown", "emoji": "❓"}


def get_coingecko_global() -> Dict[str, Any]:
    """Получить глобальную статистику рынка"""
    try:
        response = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})
        
        return {
            "success": True,
            "total_market_cap_usd": data.get("total_market_cap", {}).get("usd"),
            "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd"),
            "btc_dominance": data.get("market_cap_percentage", {}).get("btc"),
        }
    except Exception as e:
        logger.error(f"CoinGecko error: {e}")
        return {"success": False, "error": str(e)}


def run_news_analysis(symbol: str) -> Dict[str, Any]:
    """Собрать новостную информацию"""
    return {
        "success": True,
        "symbol": symbol.upper(),
        "timestamp": datetime.now().isoformat(),
        "fear_greed": get_fear_greed_index(),
        "global_market": get_coingecko_global(),
    }
