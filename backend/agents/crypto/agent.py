"""
Crypto Analyst Agent - главный агент-координатор (v2.0)

Архитектура:
1. Парсинг типа запроса (полный / модульный)
2. Параллельный запуск субагентов
3. Форматирование данных для LLM
4. LLM генерирует профессиональный отчёт

Модульные запросы:
- "индикаторы btc" / "indicators eth" - только технический анализ
- "стакан sol" / "orderbook sol" - только orderbook
- "сделки btc" / "trades btc" - только flow сделок
- "настроение eth" / "sentiment eth" - Fear&Greed + Futures
- "smc btc" / "smart money btc" - Smart Money Concepts
- "объём eth" / "volume eth" - Volume Analysis
- "mtf sol" - Multi-Timeframe Analysis
- "полный btc" / без модификатора - полный анализ
"""

import logging
import re
from typing import Dict, Any, Optional, List
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

# Импортируем новые субагенты
from backend.tools.crypto.futures_tool import get_futures_market_data
from backend.tools.crypto.smart_money_tool import analyze_smart_money
from backend.tools.crypto.mtf_analysis_tool import run_mtf_analysis
from backend.tools.crypto.volume_analysis_tool import analyze_volume

logger = logging.getLogger(__name__)

# Определяем список известных токенов для быстрого поиска
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

# Определяем паттерны для модульных запросов
QUERY_PATTERNS = {
    "indicators": ["индикатор", "indicator", "rsi", "macd", "тех анализ", "technical"],
    "orderbook": ["стакан", "orderbook", "order book", "дельт", "delta", "bid", "ask"],
    "trades": ["сделк", "trade", "flow", "поток", "whale", "кит"],
    "sentiment": ["настроен", "sentiment", "fear", "greed", "фандинг", "funding"],
    "smc": ["smc", "smart money", "смарт мани", "fvg", "imbalance", "имбаланс", "ob", "order block"],
    "volume": ["объём", "объем", "volume", "vol", "rvol"],
    "mtf": ["mtf", "мульти", "multi", "таймфрейм", "timeframe", "краткосрок", "долгосрок"],
    "levels": ["уровн", "level", "support", "resistance", "поддержк", "сопротивлен"],
    "full": ["полный", "full", "всё", "все", "анализ", "analysis", "разбор"],
}


def detect_query_type(message: str) -> str:
    """
    Определяем тип запроса пользователя на основе ключевых слов.
    :param message: Сообщение пользователя
    :return: Тип запроса (строка)
    """
    message_lower = message.lower()
    
    for query_type, patterns in QUERY_PATTERNS.items():
        for pattern in patterns:
            if pattern in message_lower:
                if query_type != "full":
                    return query_type
    
    return "full"


def extract_symbol_from_message(message: str) -> Optional[str]:
    """
    Извлекаем символ криптовалюты из сообщения.
    :param message: Сообщение пользователя
    :return: Символ пары (например, BTCUSDT) или None
    """
    message_lower = message.lower()
    
    for token, symbol in KNOWN_TOKENS.items():
        if token in message_lower:
            return symbol
    
    match = re.search(r'\b([A-Za-z]{2,10})USDT\b', message, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}USDT"
    
    matches = re.findall(r'\b([A-Z]{3,5})\b', message.upper())
    exclude = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "PRO", "TOP", "USD", "SMC", "MTF", "FVG"}
    for match in matches:
        if match not in exclude:
            return f"{match}USDT"
    
    return None


def run_full_analysis(symbol: str) -> Dict[str, Any]:
    """
    Запускаем полный анализ криптовалюты используя всех субагентов.
    :param symbol: Торговая пара
    :return: Словарь с результатами всех анализов
    """
    client = get_binance_client()
    symbol = client.normalize_symbol(symbol)
    
    logger.info(f"Running FULL analysis for {symbol}")
    
    results = {"symbol": symbol, "timestamp": datetime.now().isoformat(), "success": True, "errors": [], "query_type": "full"}
    
    # Запускаем все задачи анализа параллельно (8 субагентов)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(run_price_analysis, symbol): "price",
            executor.submit(run_trades_analysis, symbol): "trades",
            executor.submit(run_orderbook_analysis, symbol): "orderbook",
            executor.submit(run_news_analysis, symbol): "news",
            executor.submit(get_futures_market_data, symbol): "futures",
            executor.submit(analyze_smart_money, symbol, "1h", 100): "smc",
            executor.submit(run_mtf_analysis, symbol): "mtf",
            executor.submit(analyze_volume, symbol, "1h", 100): "volume",
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


def run_modular_analysis(symbol: str, query_type: str) -> Dict[str, Any]:
    """
    Запускаем модульный анализ (только выбранные компоненты).
    :param symbol: Торговая пара
    :param query_type: Тип запроса
    :return: Словарь с результатами выбранных анализов
    """
    client = get_binance_client()
    symbol = client.normalize_symbol(symbol)
    
    logger.info(f"Running {query_type.upper()} analysis for {symbol}")
    
    results = {"symbol": symbol, "timestamp": datetime.now().isoformat(), "success": True, "errors": [], "query_type": query_type}
    
    try:
        if query_type == "indicators":
            results["price"] = run_price_analysis(symbol)
            results["mtf"] = run_mtf_analysis(symbol)
        
        elif query_type == "orderbook":
            results["orderbook"] = run_orderbook_analysis(symbol)
        
        elif query_type == "trades":
            results["trades"] = run_trades_analysis(symbol)
        
        elif query_type == "sentiment":
            results["news"] = run_news_analysis(symbol)
            results["futures"] = get_futures_market_data(symbol)
        
        elif query_type == "smc":
            results["smc"] = analyze_smart_money(symbol, "1h", 100)
            # Добавляем анализ 4h для более полной картины
            results["smc_4h"] = analyze_smart_money(symbol, "4h", 100)
        
        elif query_type == "volume":
            results["volume"] = analyze_volume(symbol, "1h", 100)
            results["volume_4h"] = analyze_volume(symbol, "4h", 100)
        
        elif query_type == "mtf":
            results["mtf"] = run_mtf_analysis(symbol)
        
        elif query_type == "levels":
            results["orderbook"] = run_orderbook_analysis(symbol)
            results["smc"] = analyze_smart_money(symbol, "1h", 100)
        
        else:
            return run_full_analysis(symbol)
            
    except Exception as e:
        logger.error(f"Error in modular analysis: {e}")
        results["errors"].append(str(e))
    
    return results


def format_data_for_prompt(data: Dict[str, Any]) -> str:
    """
    Форматируем данные анализа для подачи в промпт LLM.
    :param data: Данные анализа
    :return: Отформатированная строка
    """
    lines = []
    
    symbol = data.get("symbol", "UNKNOWN")
    query_type = data.get("query_type", "full")
    
    lines.append(f"# Данные с Binance для {symbol}")
    lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC+7")
    lines.append(f"Тип запроса: {query_type}")
    lines.append("")
    
    # === ЦЕНА ===
    price = data.get("price", {})
    if price.get("success"):
        lines.append("## 💰 Цена")
        lines.append(f"- Текущая цена: ${price.get('current_price', 0):,.2f}")
        lines.append(f"- Изменение 24h: {price.get('price_change_percent_24h', 0):+.2f}%")
        lines.append(f"- High/Low 24h: ${price.get('high_24h', 0):,.2f} / ${price.get('low_24h', 0):,.2f}")
        lines.append(f"- Общий тренд: {price.get('overall_trend', 'neutral')} {price.get('trend_emoji', '')}")
        
        # Индикаторы по таймфреймам (расширенные)
        tf_analysis = price.get("timeframe_analysis", {})
        if tf_analysis:
            lines.append("### Индикаторы (12 штук) по таймфреймам:")
            for tf, tf_data in tf_analysis.items():
                indicators = tf_data.get("indicators", {})
                total = tf_data.get("bullish_count", 0) + tf_data.get("bearish_count", 0)
                signal = tf_data.get("overall_signal", "neutral")
                lines.append(f"- {tf}: Signal={signal}, Bullish={tf_data.get('bullish_count', 0)}/{total}")
                
                # Показываем ключевые индикаторы
                rsi = indicators.get("rsi", {})
                if rsi:
                    lines.append(f"  RSI: {rsi.get('value', 'N/A')} ({rsi.get('signal', '')})")
                macd = indicators.get("macd", {})
                if macd:
                    lines.append(f"  MACD: {macd.get('trend', 'N/A')}")
                bb = indicators.get("bollinger", {})
                if bb:
                    lines.append(f"  Bollinger: {bb.get('signal', 'N/A')} (pos={bb.get('position', 0):.2f})")
                supertrend = indicators.get("supertrend", {})
                if supertrend:
                    lines.append(f"  SuperTrend: {supertrend.get('signal', 'N/A')}")
        lines.append("")
    
    # === MTF ===
    mtf = data.get("mtf", {})
    if mtf.get("success"):
        lines.append("## 📊 Multi-Timeframe Analysis")
        lines.append(f"- MTF Signal: {mtf.get('mtf_signal', 'neutral')} {mtf.get('mtf_emoji', '')}")
        lines.append(f"- Консенсус: {mtf.get('consensus_text', '')}")
        
        for horizon_key in ["short", "medium", "long"]:
            h = mtf.get("horizons", {}).get(horizon_key, {})
            if h.get("success"):
                lines.append(f"- {h.get('emoji', '')} {h.get('name', '')}: {h.get('horizon_signal', '')}")
        lines.append("")
    
    # === СДЕЛКИ (расширенные) ===
    trades = data.get("trades", {})
    if trades.get("success"):
        lines.append("## 🔄 Анализ сделок")
        lines.append(f"- Всего: {trades.get('total_trades', 0)} сделок")
        lines.append(f"- Buy/Sell: {trades.get('buy_volume_ratio', 50):.1f}% / {100 - trades.get('buy_volume_ratio', 50):.1f}%")
        lines.append(f"- Давление: {trades.get('pressure', 'neutral')} {trades.get('pressure_emoji', '')}")
        lines.append(f"- Тренд: {trades.get('trend', 'neutral')} {trades.get('trend_emoji', '')}")
        
        # Временные метрики
        time_m = trades.get("time_metrics", {})
        if time_m:
            lines.append(f"- Скорость: {time_m.get('trades_per_minute', 0):.0f} trades/min {time_m.get('velocity_emoji', '')}")
            lines.append(f"- Время: {time_m.get('time_range_minutes', 0):.1f} мин")
        
        # Распределение
        size_d = trades.get("size_distribution", {})
        if size_d:
            lines.append(f"- Whale trades: {size_d.get('whale_count', 0)} ({size_d.get('whale_volume_percent', 0):.1f}% объёма)")
        
        # Киты
        large = trades.get("large_trades", {})
        if large:
            lines.append(f"- 🐋 Киты: {large.get('whale_direction', 'neutral')} {large.get('whale_emoji', '')}")
            lines.append(f"  Buy: {large.get('buy_count', 0)}, Sell: {large.get('sell_count', 0)}")
        
        # Ratios
        ratios = trades.get("ratios", {})
        if ratios:
            lines.append(f"- Buy/Sell Ratio: {ratios.get('buy_sell_volume_ratio', 1):.2f}")
        lines.append("")
    
    # === СТАКАН (с 7 дельтами) ===
    orderbook = data.get("orderbook", {})
    if orderbook.get("success"):
        lines.append("## 📈 Стакан")
        lines.append(f"- Цена: ${orderbook.get('current_price', 0):,.2f}")
        lines.append(f"- Spread: {orderbook.get('spread_percent', 0):.4f}%")
        lines.append(f"- Bid/Ask ratio: {orderbook.get('bid_ask_ratio', 1):.2f}")
        lines.append(f"- Sentiment: {orderbook.get('sentiment', 'neutral')} {orderbook.get('sentiment_emoji', '')}")
        
        # Дельты (7 уровней)
        deltas = orderbook.get("deltas", {})
        if deltas:
            lines.append("### Дельты по уровням:")
            for level, d in deltas.items():
                emoji = "🟢" if d.get("pressure") == "buy" else "🔴"
                lines.append(f"- {level}: Delta={d.get('delta', 0):+.2f}, {emoji} {d.get('pressure', '')}")
        
        # Уровни
        supports = orderbook.get("support_levels", [])[:3]
        resistances = orderbook.get("resistance_levels", [])[:3]
        if supports:
            support_prices = ', '.join([f"${s.get('price', 0):,.0f}" for s in supports])
            lines.append(f"### Поддержка: {support_prices}")
        if resistances:
            resistance_prices = ', '.join([f"${r.get('price', 0):,.0f}" for r in resistances])
            lines.append(f"### Сопротивление: {resistance_prices}")
        lines.append("")
    
    # === VOLUME ===
    volume = data.get("volume", {})
    if volume.get("success"):
        lines.append("## 📊 Volume Analysis")
        vd = volume.get("volume_delta", {})
        if vd:
            lines.append(f"- Volume Delta: {vd.get('delta_percent', 0):+.1f}% {vd.get('emoji', '')}")
        rv = volume.get("relative_volume", {})
        if rv:
            lines.append(f"- Relative Volume: {rv.get('rvol', 1):.2f}x {rv.get('emoji', '')}")
        vp = volume.get("volume_profile", {})
        if vp:
            lines.append(f"- POC (Point of Control): ${vp.get('poc', 0):,.2f}")
            lines.append(f"- Value Area: ${vp.get('val', 0):,.2f} - ${vp.get('vah', 0):,.2f}")
        vt = volume.get("volume_trend", {})
        if vt:
            lines.append(f"- Trend: {vt.get('trend', '')} ({vt.get('change_percent', 0):+.1f}%)")
        lines.append("")
    
    # === SMART MONEY ===
    smc = data.get("smc", {})
    if smc.get("success"):
        lines.append("## 🎯 Smart Money Concepts")
        struct = smc.get("structure", {})
        if struct:
            lines.append(f"- Structure: {struct.get('structure', 'unknown')} {struct.get('trend_emoji', '')}")
            lines.append(f"- Trend: {struct.get('trend', 'neutral')}")
            lines.append(f"- HH={struct.get('hh_count', 0)}, HL={struct.get('hl_count', 0)}, LH={struct.get('lh_count', 0)}, LL={struct.get('ll_count', 0)}")
        
        fvg = smc.get("fair_value_gaps", {})
        if fvg:
            lines.append(f"- FVG (незаполненные): {fvg.get('unfilled', 0)} (Bull: {fvg.get('bullish', 0)}, Bear: {fvg.get('bearish', 0)})")
        
        ob = smc.get("order_blocks", {})
        if ob:
            lines.append(f"- Order Blocks: {ob.get('total', 0)} (Bull: {ob.get('bullish', 0)}, Bear: {ob.get('bearish', 0)})")
        
        liq = smc.get("liquidity_zones", {})
        if liq:
            buy_stops = liq.get("buy_stops", [])
            sell_stops = liq.get("sell_stops", [])
            if buy_stops:
                buy_stops_str = ', '.join([f"${s.get('price', 0):,.0f}" for s in buy_stops[:2]])
                lines.append(f"- Buy Stops (над хаями): {buy_stops_str}")
            if sell_stops:
                sell_stops_str = ', '.join([f"${s.get('price', 0):,.0f}" for s in sell_stops[:2]])
                lines.append(f"- Sell Stops (под лоями): {sell_stops_str}")
        
        lines.append(f"- SMC Signal: {smc.get('overall_signal', 'neutral')} {smc.get('overall_emoji', '')}")
        lines.append("")
    
    # === FUTURES (Funding + OI) ===
    futures = data.get("futures", {})
    if futures.get("success"):
        lines.append("## 📈 Futures Data")
        fr = futures.get("funding_rate", {})
        if fr.get("success"):
            lines.append(f"- Funding Rate: {fr.get('funding_rate_percent', 0):.4f}% {fr.get('sentiment_emoji', '')}")
            lines.append(f"- {fr.get('interpretation', '')}")
        
        oi = futures.get("oi_history", {})
        if oi.get("success"):
            lines.append(f"- Open Interest: {oi.get('oi_trend', '')} ({oi.get('oi_change_percent', 0):+.1f}%) {oi.get('oi_emoji', '')}")
        
        ls = futures.get("long_short_ratio", {})
        if ls.get("success"):
            lines.append(f"- Long/Short Ratio: {ls.get('long_short_ratio', 1):.2f} {ls.get('sentiment_emoji', '')}")
            lines.append(f"  Long: {ls.get('long_percent', 50):.1f}%, Short: {ls.get('short_percent', 50):.1f}%")
        
        lines.append(f"- Futures Signal: {futures.get('overall_sentiment', 'neutral')} {futures.get('overall_emoji', '')}")
        lines.append("")
    
    # === NEWS ===
    news = data.get("news", {})
    if news.get("success", True):
        lines.append("## 📰 Market Context")
        fng = news.get("fear_greed", {})
        if fng.get("value"):
            lines.append(f"- Fear & Greed: {fng.get('value')} ({fng.get('classification', '')}) {fng.get('emoji', '')}")
        gm = news.get("global_market", {})
        if gm.get("success"):
            mc = gm.get("total_market_cap_usd", 0)
            if mc:
                lines.append(f"- Total Market Cap: ${mc/1e12:.2f}T")
            lines.append(f"- BTC Dominance: {gm.get('btc_dominance', 0):.1f}%")
        lines.append("")
    
    # === ОШИБКИ ===
    if data.get("errors"):
        lines.append("## ⚠️ Ошибки")
        for err in data["errors"]:
            lines.append(f"- {err}")
    
    return "\n".join(lines)


def create_crypto_analyst_agent(llm_provider: BaseLLMProvider, session_path: Path) -> Agent:
    """
    Создаем главного агента Crypto Analyst v2.0.
    :param llm_provider: Провайдер LLM
    :param session_path: Путь к сессии
    :return: Экземпляр агента
    """
    
    def get_instruction_with_context(state: AgentState) -> str:
        """
        Динамически формируем промпт с реальными данными.
        :param state: Состояние агента
        :return: Инструкция для LLM
        """
        
        user_input = state.get("current_user_input", "")
        
        # Извлекаем символ и тип запроса
        symbol = extract_symbol_from_message(user_input)
        query_type = detect_query_type(user_input)
        
        if symbol:
            logger.info(f"Symbol: {symbol}, Query type: {query_type}")
            
            # Запускаем соответствующий анализ
            if query_type == "full":
                analysis_data = run_full_analysis(symbol)
            else:
                analysis_data = run_modular_analysis(symbol, query_type)
            
            state.set("analysis_data", analysis_data)
            
            # Форматируем данные
            data_text = format_data_for_prompt(analysis_data)
            
            # Определяем фокус промпта в зависимости от типа запроса
            focus_instructions = {
                "indicators": "Сфокусируйся на технических индикаторах. Дай подробный разбор каждого индикатора и общий вывод.",
                "orderbook": "Сфокусируйся на анализе стакана. Разбери дельты, уровни поддержки/сопротивления, дисбалансы.",
                "trades": "Сфокусируйся на потоке сделок. Разбери давление, активность китов, скорость сделок.",
                "sentiment": "Сфокусируйся на настроении рынка. Разбери Fear&Greed, Funding Rate, Long/Short Ratio.",
                "smc": "Сфокусируйся на Smart Money Concepts. Разбери структуру рынка, FVG, Order Blocks, зоны ликвидности.",
                "volume": "Сфокусируйся на анализе объёмов. Разбери Volume Delta, Relative Volume, Point of Control.",
                "mtf": "Сфокусируйся на мульти-таймфрейм анализе. Разбери сигналы по каждому горизонту.",
                "levels": "Сфокусируйся на ключевых уровнях. Укажи поддержку, сопротивление, зоны ликвидности.",
                "full": "Дай полный комплексный анализ на основе всех данных.",
            }
            
            focus = focus_instructions.get(query_type, focus_instructions["full"])
            
            return f"""Ты - профессиональный криптовалютный аналитик уровня institutional trader.

Текущая дата: {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC+7
Тип запроса: {query_type}

Ниже представлены РЕАЛЬНЫЕ данные с Binance API. Используй ТОЛЬКО эти данные.

{data_text}

ЗАДАЧА: {focus}

ФОРМАТ ОТЧЁТА:
1. Emoji для визуализации
2. Точные цифры из данных
3. Интерпретация каждого показателя
4. Scoring: оцени сигнал от -100 (сильно медвежий) до +100 (сильно бычий)
5. Итоговый вердикт: STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL
6. Ключевые уровни и зоны внимания
7. Риски и предупреждения

ВАЖНО:
- Цены должны точно соответствовать данным
- Будь объективен, указывай и бычьи и медвежьи сигналы
- Если данные противоречивы - укажи это

Отвечай на русском языке."""

        else:
            return f"""Ты - профессиональный криптовалютный аналитик.

Текущая дата: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Пользователь не указал какую криптовалюту анализировать.
Попроси уточнить и предложи варианты.

Поддерживаемые типы анализа:
- \"анализ BTC\" - полный анализ
- \"индикаторы ETH\" - только технический анализ
- \"стакан SOL\" - анализ orderbook
- \"сделки BTC\" - анализ потока сделок
- \"настроение ETH\" - sentiment + Funding Rate
- \"smc BTC\" - Smart Money Concepts
- \"объём SOL\" - анализ объёмов
- \"mtf ETH\" - мульти-таймфрейм

Отвечай на русском языке."""
    
    return Agent(
        name="crypto_analyst",
        llm_provider=llm_provider,
        instruction=get_instruction_with_context,
        temperature=0.3,
    )