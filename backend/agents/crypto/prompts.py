"""
Prompts для Crypto Analyst Agent
"""

from datetime import datetime

FINAL_REPORT_TEMPLATE = """
# 📊 Комплексный анализ {symbol}

**Дата:** {timestamp}

---

## 💰 Цена
{price_section}

---

## 📈 Технический анализ
{technical_section}

---

## 🔄 Анализ сделок
{trades_section}

---

## 📊 Анализ стакана
{orderbook_section}

---

## 📰 Рыночный контекст
{news_section}

---

## 🎯 Выводы
{conclusion_section}

---

*Данные получены с Binance API. Анализ носит информационный характер.*
"""


def format_final_report(symbol: str, price_data: dict, trades_data: dict, 
                       orderbook_data: dict, news_data: dict) -> str:
    """Форматировать финальный отчёт"""
    
    # Цена
    price_section = "❌ Данные недоступны"
    if price_data and price_data.get("success"):
        p = price_data
        change_emoji = "🟢" if p.get("price_change_percent_24h", 0) > 0 else "🔴"
        price_section = f"""**Цена:** ${p.get('current_price', 0):,.2f}
**24h:** {change_emoji} {p.get('price_change_percent_24h', 0):+.2f}%
**Диапазон:** ${p.get('low_24h', 0):,.0f} - ${p.get('high_24h', 0):,.0f}
**{p.get('trend_emoji', '➡️')} Тренд:** {p.get('overall_trend', 'neutral').upper()}"""
    
    # Технический анализ
    technical_section = "❌ Данные недоступны"
    if price_data and price_data.get("success"):
        lines = ["| Таймфрейм | RSI | MACD | Сигнал |", "|-----------|-----|------|--------|"]
        for tf, tf_data in price_data.get("timeframe_analysis", {}).items():
            indicators = tf_data.get("indicators", {})
            rsi = indicators.get("rsi", {}).get("value", "-")
            macd = indicators.get("macd", {}).get("trend", "-")
            signal = tf_data.get("overall_signal", "neutral")
            emoji = "🟢" if signal == "bullish" else "🔴" if signal == "bearish" else "⚪"
            lines.append(f"| {tf} | {rsi} | {macd} | {emoji} |")
        technical_section = "\n".join(lines)
    
    # Сделки
    trades_section = "❌ Данные недоступны"
    if trades_data and trades_data.get("success"):
        t = trades_data
        trades_section = f"""{t.get('pressure_emoji', '⚪')} **Давление:** {t.get('pressure', 'neutral')}
**Buy/Sell:** {t.get('buy_volume_ratio', 50):.1f}% / {100 - t.get('buy_volume_ratio', 50):.1f}%
🐋 **Киты:** {t.get('large_trades', {}).get('whale_direction', 'unknown')}"""
    
    # Стакан
    orderbook_section = "❌ Данные недоступны"
    if orderbook_data and orderbook_data.get("success"):
        o = orderbook_data
        orderbook_section = f"""{o.get('sentiment_emoji', '⚪')} **Sentiment:** {o.get('sentiment', 'neutral')}
**Bid/Ask:** {o.get('bid_ask_ratio', 1):.2f}
{o.get('levels_text', '')}"""
    
    # Новости
    news_section = "❌ Данные недоступны"
    if news_data and news_data.get("success", True):
        fng = news_data.get("fear_greed", {})
        global_data = news_data.get("global_market", {})
        lines = []
        if fng.get("value"):
            lines.append(f"{fng.get('emoji', '❓')} **Fear & Greed:** {fng.get('value')} - {fng.get('classification')}")
        if global_data.get("success"):
            mc = global_data.get("total_market_cap_usd", 0)
            if mc:
                lines.append(f"🌍 **Market Cap:** ${mc/1e12:.2f}T")
        if lines:
            news_section = "\n".join(lines)
    
    # Выводы
    bullish = 0
    bearish = 0
    if price_data and price_data.get("overall_trend") == "bullish":
        bullish += 2
    if price_data and price_data.get("overall_trend") == "bearish":
        bearish += 2
    if trades_data and "buy" in trades_data.get("pressure", ""):
        bullish += 1
    if trades_data and "sell" in trades_data.get("pressure", ""):
        bearish += 1
    if orderbook_data and "bullish" in orderbook_data.get("sentiment", ""):
        bullish += 1
    if orderbook_data and "bearish" in orderbook_data.get("sentiment", ""):
        bearish += 1
    
    if bullish > bearish + 1:
        conclusion_section = "🟢 **БЫЧИЙ** - Большинство индикаторов указывают на рост"
    elif bearish > bullish + 1:
        conclusion_section = "🔴 **МЕДВЕЖИЙ** - Большинство индикаторов указывают на снижение"
    else:
        conclusion_section = "⚪ **НЕЙТРАЛЬНЫЙ** - Смешанные сигналы"
    
    return FINAL_REPORT_TEMPLATE.format(
        symbol=symbol,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        price_section=price_section,
        technical_section=technical_section,
        trades_section=trades_section,
        orderbook_section=orderbook_section,
        news_section=news_section,
        conclusion_section=conclusion_section,
    )
