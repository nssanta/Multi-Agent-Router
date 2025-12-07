"""
Trades Analyst - анализ потока сделок
"""

from typing import Dict, Any
from backend.tools.crypto.trades_analysis_tool import analyze_trades


def run_trades_analysis(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    """Выполнить анализ потока сделок"""
    return analyze_trades(symbol, limit)
