"""
Orderbook Analyst - анализ стакана
"""

from typing import Dict, Any
from backend.tools.crypto.orderbook_analysis_tool import analyze_orderbook


def run_orderbook_analysis(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """Выполнить анализ стакана"""
    return analyze_orderbook(symbol, limit)
