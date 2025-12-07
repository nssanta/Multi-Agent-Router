# 🤖 Multi-Agent AI Router

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6.svg)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Модульная платформа AI-агентов с поддержкой нескольких LLM-провайдеров.**

> 📚 *Это демо-проект в образовательных и исследовательских целях.*

🇬🇧 [English version](README.md)

---

## 🎯 В чём крутость

| Фича | Описание |
|------|----------|
| **🔌 Plug & Play LLM** | Переключайтесь между Gemini, OpenRouter или любым OpenAI-совместимым API |
| **🧩 Модульные агенты** | Каждый агент независим — добавьте свой за минуты |
| **🛠️ Реальное выполнение** | Агенты не просто болтают — они *делают*: ищут, кодят, анализируют |
| **📊 Live крипто-данные** | Интеграция с Binance API — цены, стакан, сделки в реальном времени |
| **🐳 Docker Sandbox** | Выполнение кода в изолированных контейнерах — безопасно и воспроизводимо |
| **⚡ Native Tool Calling** | Gemini 2.5 Pro использует нативные вызовы функций |

---

## 🤖 Агенты

### 🔍 Dialog Agent
*Интеллектуальный диалоговый агент с веб-возможностями*

- **Умный поиск** — Мульти-источниковый поиск с агрегацией результатов
- **Чтение страниц** — Извлечение и суммаризация контента с любого URL
- **Осведомлённость о контексте** — Сохраняет историю диалога и состояние сессии

---

### 🧠 Coder Agent
*Полнофункциональный ассистент для кодинга, который реально выполняет код*

![Coder Agent](coder_screen.png)

- **Файловые операции** — Создание, чтение, листинг файлов в изолированном workspace
- **Выполнение кода** — Запуск Python в Docker песочнице
- **Многофайловые проекты** — Импорт между файлами, создание полноценных проектов
- **Native Tool Calling** — Gemini 2.5 Pro использует нативные вызовы функций

**Пример:**
```
Пользователь: Посчитай числа Фибоначчи до 100

Агент: Создам и запущу Python скрипт.
[Создаёт fibonacci.py → Выполняет → Возвращает результат]

Вывод: [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
```

---

### 📊 Crypto Analyst Agent
*Профессиональный криптоаналитик с данными Binance в реальном времени*

![Crypto Analyst](crypto_screen.png)

**Данные в реальном времени с Binance API:**
- 💰 **Цена и свечи** — Текущая цена, изменение 24h, мульти-таймфрейм
- 📈 **Технические индикаторы** — RSI, MACD, EMA на 5m/1h/4h/1d
- 📊 **Анализ стакана** — Дельты на 1.5%, 5%, 15%, 60% от цены
- 🔄 **Поток сделок** — Buy/sell давление, активность китов
- 😨 **Рыночный контекст** — Fear & Greed Index, капитализация рынка

**Пример ответа:**
```
📊 Отчёт по BTC/USDT | 2025-12-07

💰 Цена: $88,993.33 (-0.80% 24h)
📈 Тренд: Медвежий (3/4 таймфрейма)

Технический анализ:
- RSI 1h: 40.15 (нейтрально-слабый)
- MACD: медвежий на 1h/4h/1d

Дельты стакана:
- 1.5%: Bid=85.99, Ask=81.22, 🟢 давление покупателей
- 5%:   Bid=85.99, Ask=81.22, 🟢 давление покупателей

Поток сделок:
- Buy: 259 сделок, Sell: 741 сделок
- Ratio по объёму: 10.2% buy
- Направление китов: sell

😨 Fear & Greed: 20 (Extreme Fear)
🔑 Поддержка: $88,900 | Сопротивление: $89,100
```

---

## 🏗️ Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Frontend  │────▶│   FastAPI    │────▶│   LLM Provider  │
│   (React)   │     │   (routes)   │     │ Gemini/OpenRouter│
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌─────────┐
              │  Agent  │   │ Session │
              │ Dialog/ │   │ Manager │
              │ Coder/  │   └─────────┘
              │ Crypto  │
              └────┬────┘
                   ▼
              ┌─────────┐
              │  Tools  │
              │ search/ │
              │ files/  │
              │ code/   │
              │ crypto  │
              └─────────┘
```

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/nssanta/Multi-Agent-Router.git
cd Multi-Agent-Router
cp .env.example .env
# Добавьте API ключи в .env
docker compose up --build
```

Открыть: **http://localhost:3000**

---

## ⚙️ Конфигурация

```env
# Обязательные
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key

# Опциональные
LLM_PROVIDER=gemini          # или openrouter
LLM_MODEL=gemini-2.5-pro     # модель по умолчанию
```

---

## 🔧 Расширение системы

### Добавить нового агента

```python
# backend/agents/my_agent/agent.py
def create_my_agent(llm_provider, session_path):
    return Agent(
        name="my_agent",
        llm_provider=llm_provider,
        instruction="Ваш кастомный промпт",
        tool_definitions=[...],
    )
```

### Добавить новый инструмент

```python
# backend/tools/my_tool.py
def my_tool(param: str) -> str:
    """Описание инструмента для LLM"""
    return f"Result: {param}"
```

---

## 📁 Структура проекта

```
backend/
├── agents/           # Dialog, Coder, Crypto агенты
│   ├── dialog/       # Диалоговый агент
│   ├── coder/        # Агент выполнения кода
│   └── crypto/       # Криптоаналитик
├── api/              # FastAPI роуты
├── core/             # LLM провайдеры, сессии, executor
└── tools/            # Инструменты агентов
    ├── web/          # Поиск, чтение страниц
    └── crypto/       # Binance API, индикаторы

frontend/
├── src/components/   # React компоненты
└── src/services/     # API клиент
```

Полная техническая документация: [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)

---

## 📄 Лицензия

MIT
