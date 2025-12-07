# 🤖 Multi-Agent AI Router

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6.svg)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Модульная платформа для создания AI-агентов с поддержкой нескольких LLM-провайдеров.**

![Coder Agent](coder_screen.png)

---

## Что это

Расширяемая система агентов, где каждый компонент можно заменить или модифицировать:

| Компонент | Назначение | Можно заменить на |
|-----------|------------|-------------------|
| **LLM Provider** | Генерация ответов | Любой OpenAI-совместимый API |
| **Agent** | Логика обработки | Свой агент с кастомными промптами |
| **Tools** | Инструменты агента | Любые Python функции |
| **Code Executor** | Выполнение кода | Docker sandbox, VM, или remote API |
| **Frontend** | UI интерфейс | Любой React/Vue/Svelte клиент |

---

## Архитектура

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
              │ Coder   │   └─────────┘
              └────┬────┘
                   ▼
              ┌─────────┐
              │  Tools  │
              │ search/ │
              │ files/  │
              │ code    │
              └─────────┘
```

---

## Агенты

### Dialog Agent
- Умный поиск в интернете (`SEARCH`, `SMART_SEARCH`)
- Чтение веб-страниц (`READ`)
- Мультимодельная поддержка

### Coder Agent  
- Создание файлов (`write_file`)
- Чтение файлов (`read_file`)
- Выполнение Python (`run_code`)
- Native Tool Calling для Gemini

---

## Быстрый старт

```bash
git clone https://github.com/nssanta/Multi-Agent-Router.git
cd Multi-Agent-Router
cp .env.example .env
# Добавьте API ключи в .env
docker compose up --build
```

Открыть: **http://localhost:3000**

---

## Расширение системы

### Добавить нового агента

```python
# backend/agents/my_agent/agent.py
def create_my_agent(llm_provider, session_path):
    return Agent(
        name="my_agent",
        llm_provider=llm_provider,
        instruction="Your custom prompt here",
        tool_definitions=[...],  # Ваши инструменты
    )
```

### Добавить новый инструмент

```python
# backend/tools/my_tool.py
def my_tool(param1: str, param2: int) -> str:
    """Описание инструмента для LLM"""
    return f"Result: {param1} {param2}"
```

### Добавить LLM провайдера

```python
# backend/core/llm_provider.py
class MyProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str:
        # Ваша логика
        pass
```

---

## Конфигурация

```env
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-pro
```

---

## Структура проекта

```
backend/
├── agents/           # Агенты (dialog, coder)
├── api/              # FastAPI роуты
├── core/             # LLM, sessions, executor
└── tools/            # Инструменты агентов

frontend/
├── src/components/   # React компоненты
└── src/services/     # API клиент
```

Подробности в [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)

---

## Лицензия

MIT
