"""
Crypto Analyst Agent - главный агент-координатор

Архитектура:
1. В instruction получаем реальные данные с Binance
2. Передаём данные в промпт для LLM
3. LLM анализирует и форматирует отчёт
"""

import logging
import re
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.core.agent_framework import Agent, AgentState
from backend.core.llm_provider import BaseLLMProvider
from backend.tools.crypto.binance_client import get_binance_client

from .subagents.price_analyst import run_price_analysis
from .subagents.trades_analyst import run_trades_analysis
from .subagents.orderbook_analyst import run_orderbook_analysis
from .subagents.news_analyst import run_news_analysis

logger = logging.getLogger(__name__)

# Известные токены
KNOWN_TOKENS = {
    "btc": "BTCUSDT", "bitcoin": "BTCUSDT",
    "eth": "ETHUSDT", "ethereum": "ETHUSDT",
    "sol": "SOLUSDT", "solana": "SOLUSDT",
    "bnb": "BNBUSDT", "xrp": "XRPUSDT",
    "ada": "ADAUSDT", "doge": "DOGEUSDT",
    "dot": "DOTUSDT", "matic": "MATICUSDT",
    "link": "LINKUSDT", "avax": "AVAXUSDT",
    "ton": "TONUSDT", "sui": "SUIUSDT",
    "arb": "ARBUSDT", "op": "OPUSDT",
    "pepe": "PEPEUSDT", "shib": "SHIBUSDT",
}


def extract_symbol_from_message(message: str) -> Optional[str]:
    """
    Извлекаем символ криптовалюты из сообщения.
    :param message: сообщение пользователя
    :return: символ пары (например, BTCUSDT) или None
    """
    message_lower = message.lower()
    
    for token, symbol in KNOWN_TOKENS.items():
        if token in message_lower:
            return symbol
    
    # Поиск паттерна XXXUSDT
    match = re.search(r'\b([A-Za-z]{2,10})USDT\b', message, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}USDT"
    
    # Поиск 3-5 букв
    matches = re.findall(r'\b([A-Z]{3,5})\b', message.upper())
    exclude = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "PRO", "TOP", "USD"}
    for match in matches:
        if match not in exclude:
            return f"{match}USDT"
    
    return None


def run_full_analysis(symbol: str) -> Dict[str, Any]:
    """
    Запускаем полный анализ криптовалюты.
    :param symbol: торговая пара (например, BTCUSDT)
    :return: словарь с результатами анализа
    """
    client = get_binance_client()
    symbol = client.normalize_symbol(symbol)
    
    logger.info(f"Running full analysis for {symbol}")
    
    results = {"symbol": symbol, "timestamp": datetime.now().isoformat(), "success": True, "errors": []}
    
    # Параллельный запуск анализов
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_price_analysis, symbol): "price",
            executor.submit(run_trades_analysis, symbol): "trades",
            executor.submit(run_orderbook_analysis, symbol): "orderbook",
            executor.submit(run_news_analysis, symbol): "news",
        }
        
        for future in as_completed(futures):
            analysis_type = futures[future]
            try:
                results[analysis_type] = future.result()
                logger.info(f"{analysis_type} analysis completed")
            except Exception as e:
                logger.error(f"{analysis_type} error: {e}")
                results[analysis_type] = {"success": False, "error": str(e)}
                results["errors"].append(f"{analysis_type}: {str(e)}")
    
    return results


def format_data_for_prompt(data: Dict[str, Any]) -> str:
    """
    Форматируем данные анализа для промпта.
    :param data: данные анализа
    :return: отформатированная строка
    """
    lines = []
    
    symbol = data.get("symbol", "UNKNOWN")
    lines.append(f"# Реальные данные с Binance для {symbol}")
    lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC+7")
    lines.append("")
    
    # Цена
    price = data.get("price", {})
    if price.get("success"):
        lines.append("## Цена")
        lines.append(f"- Текущая цена: ${price.get('current_price', 0):,.2f}")
        lines.append(f"- Изменение 24h: {price.get('price_change_percent_24h', 0):+.2f}%")
        lines.append(f"- High 24h: ${price.get('high_24h', 0):,.2f}")
        lines.append(f"- Low 24h: ${price.get('low_24h', 0):,.2f}")
        lines.append(f"- Общий тренд: {price.get('overall_trend', 'neutral')}")
        lines.append(f"- Бычьих ТФ: {price.get('bullish_timeframes', 0)}, Медвежьих: {price.get('bearish_timeframes', 0)}")
        
        # Индикаторы по таймфреймам
        tf_analysis = price.get("timeframe_analysis", {})
        if tf_analysis:
            lines.append("### Индикаторы по таймфреймам:")
            for tf, tf_data in tf_analysis.items():
                indicators = tf_data.get("indicators", {})
                rsi = indicators.get("rsi", {}).get("value", "N/A")
                macd = indicators.get("macd", {}).get("trend", "N/A")
                signal = tf_data.get("overall_signal", "neutral")
                lines.append(f"- {tf}: RSI={rsi}, MACD={macd}, Signal={signal}")
        lines.append("")
    else:
        lines.append(f"## Цена: ОШИБКА - {price.get('error', 'unknown')}")
    
    # Сделки - ДЕТАЛЬНО
    trades = data.get("trades", {})
    if trades.get("success"):
        lines.append("## Анализ сделок (последние 1000)")
        lines.append(f"- Всего сделок: {trades.get('total_trades', 0)}")
        lines.append(f"- Buy: {trades.get('buy_count', 0)} сделок, Sell: {trades.get('sell_count', 0)} сделок")
        lines.append(f"- Buy volume: {trades.get('buy_volume', 0):.4f}, Sell volume: {trades.get('sell_volume', 0):.4f}")
        lines.append(f"- Buy/Sell ratio по объёму: {trades.get('buy_volume_ratio', 50):.1f}%")
        lines.append(f"- Давление: {trades.get('pressure', 'neutral')} {trades.get('pressure_emoji', '')}")
        lines.append(f"- Тренд потока: {trades.get('trend', 'neutral')} {trades.get('trend_emoji', '')}")
        large = trades.get("large_trades", {})
        if large:
            lines.append(f"- Крупные сделки (whales): {large.get('count', 0)} шт")
            lines.append(f"  - Buy крупные: {large.get('buy_count', 0)}, Sell крупные: {large.get('sell_count', 0)}")
            lines.append(f"  - Направление китов: {large.get('whale_direction', 'unknown')}")
        lines.append("")
    
    # Стакан - ДЕТАЛЬНО С ДЕЛЬТАМИ
    orderbook = data.get("orderbook", {})
    if orderbook.get("success"):
        lines.append("## Анализ стакана")
        lines.append(f"- Текущая цена: ${orderbook.get('current_price', 0):,.2f}")
        lines.append(f"- Best Bid: ${orderbook.get('best_bid', 0):,.2f}")
        lines.append(f"- Best Ask: ${orderbook.get('best_ask', 0):,.2f}")
        lines.append(f"- Spread: ${orderbook.get('spread', 0):.2f} ({orderbook.get('spread_percent', 0):.4f}%)")
        lines.append(f"- Total Bid Volume: {orderbook.get('total_bid_volume', 0):.2f}")
        lines.append(f"- Total Ask Volume: {orderbook.get('total_ask_volume', 0):.2f}")
        lines.append(f"- Bid/Ask ratio: {orderbook.get('bid_ask_ratio', 1):.2f}")
        lines.append(f"- Sentiment: {orderbook.get('sentiment', 'neutral')} {orderbook.get('sentiment_emoji', '')}")
        lines.append(f"- Глубина: {orderbook.get('depth_analysis', 'unknown')} {orderbook.get('depth_emoji', '')}")
        
        # ДЕЛЬТЫ ПО УРОВНЯМ - ВАЖНО!
        deltas = orderbook.get("deltas", {})
        if deltas:
            lines.append("")
            lines.append("### Дельты стакана по уровням от цены:")
            for level, delta_data in deltas.items():
                bid_vol = delta_data.get('bid_volume', 0)
                ask_vol = delta_data.get('ask_volume', 0)
                delta = delta_data.get('delta', 0)
                pressure = delta_data.get('pressure', 'neutral')
                imbalance = delta_data.get('imbalance_ratio', 1)
                emoji = "🟢" if pressure == "buy" else "🔴"
                lines.append(f"- {level}: Bid={bid_vol:.2f}, Ask={ask_vol:.2f}, Delta={delta:+.2f}, {emoji} {pressure} (ratio={imbalance:.2f})")
        
        # Уровни поддержки/сопротивления
        lines.append("")
        supports = orderbook.get("support_levels", [])[:5]
        resistances = orderbook.get("resistance_levels", [])[:5]
        if supports:
            lines.append("### Уровни поддержки (крупные bid заявки):")
            for s in supports:
                lines.append(f"  - ${s.get('price', 0):,.2f} (volume: {s.get('volume', 0):.4f})")
        if resistances:
            lines.append("### Уровни сопротивления (крупные ask заявки):")
            for r in resistances:
                lines.append(f"  - ${r.get('price', 0):,.2f} (volume: {r.get('volume', 0):.4f})")
        lines.append("")
    
    # Новости
    news = data.get("news", {})
    if news.get("success", True):
        lines.append("## Рыночный контекст")
        fng = news.get("fear_greed", {})
        if fng.get("value"):
            lines.append(f"- Fear & Greed Index: {fng.get('value')} ({fng.get('classification', 'Unknown')})")
        global_data = news.get("global_market", {})
        if global_data.get("success"):
            mc = global_data.get("total_market_cap_usd", 0)
            if mc:
                lines.append(f"- Total Market Cap: ${mc/1e12:.2f}T")
            lines.append(f"- BTC Dominance: {global_data.get('btc_dominance', 0):.1f}%")
        lines.append("")
    
    # Ошибки
    if data.get("errors"):
        lines.append("## Ошибки")
        for err in data["errors"]:
            lines.append(f"- {err}")
    
    return "\n".join(lines)


def create_crypto_analyst_agent(llm_provider: BaseLLMProvider, session_path: Path) -> Agent:
    """
    Создаем главного агента Crypto Analyst.
    :param llm_provider: LLM провайдер
    :param session_path: путь к сессии
    :return: объект агента
    """
    
    def get_instruction_with_context(state: AgentState) -> str:
        """
        Динамически формируем промпт с реальными данными.
        :param state: состояние агента
        :return: инструкция с контекстом
        """
        
        user_input = state.get("current_user_input", "")
        
        # Извлекаем символ из сообщения пользователя
        symbol = extract_symbol_from_message(user_input)
        
        if symbol:
            logger.info(f"Extracted symbol: {symbol}, running analysis...")
            
            # ВАЖНО: Получаем РЕАЛЬНЫЕ данные с Binance СЕЙЧАС
            analysis_data = run_full_analysis(symbol)
            state.set("analysis_data", analysis_data)
            
            # Форматируем данные для промпта
            data_text = format_data_for_prompt(analysis_data)
            
            return f"""Ты - профессиональный криптовалютный аналитик.

Текущая дата: {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC+7

Ниже представлены РЕАЛЬНЫЕ данные с Binance API. Используй ТОЛЬКО эти данные для анализа.
НЕ ВЫДУМЫВАЙ цены и данные! Используй только то, что я тебе дал.

{data_text}

Твоя задача: на основе ЭТИХ РЕАЛЬНЫХ ДАННЫХ создать красивый структурированный отчёт.

Формат отчёта:
1. Используй emoji для визуализации
2. Укажи ТОЧНУЮ цену из данных выше
3. Дай интерпретацию индикаторов
4. Сделай вывод (бычий/медвежий/нейтральный)
5. Укажи ключевые уровни поддержки/сопротивления

ВАЖНО: Цена должна точно соответствовать данным выше!

Отвечай на русском языке."""

        else:
            return f"""Ты - профессиональный криптовалютный аналитик.

Текущая дата: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Пользователь не указал какую криптовалюту анализировать.
Попроси уточнить, какую монету он хочет проанализировать.

Примеры: BTC, ETH, SOL, BNB, XRP, DOGE, etc.

Отвечай на русском языке."""
    
    return Agent(
        name="crypto_analyst",
        llm_provider=llm_provider,
        instruction=get_instruction_with_context,
        temperature=0.3,  # Низкая температура для точности
    )
