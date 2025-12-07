# 🤖 Multi-Agent AI Router

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6.svg)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Modular AI agent platform with multi-provider LLM support.**

🇷🇺 [Русская версия](README_RU.md)

![Coder Agent](coder_screen.png)

---

## What Is This

A flexible, extensible framework for building AI agents. Every component is modular and replaceable:

| Component | Purpose | Replace With |
|-----------|---------|--------------|
| **LLM Provider** | Response generation | Any OpenAI-compatible API |
| **Agent** | Processing logic | Custom agent with your prompts |
| **Tools** | Agent capabilities | Any Python functions |
| **Code Executor** | Code execution | Docker sandbox, VM, remote API |
| **Frontend** | User interface | Any React/Vue/Svelte client |

---

## Agents

### 🔍 Dialog Agent
Intelligent conversational agent with web capabilities:
- **Smart Search** — Multi-source web search with result aggregation
- **Page Reading** — Extract and summarize content from any URL
- **Context Awareness** — Maintains conversation history and session state

### 🧠 Coder Agent
Full-featured coding assistant that actually executes code:
- **File Operations** — Create, read, list files in isolated workspace
- **Code Execution** — Run Python in sandboxed Docker environment
- **Native Tool Calling** — Gemini 2.5 Pro uses native function calling for reliable tool execution
- **Multi-File Projects** — Import between files, build complete projects

---

## Architecture

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

## Quick Start

```bash
git clone https://github.com/nssanta/Multi-Agent-Router.git
cd Multi-Agent-Router
cp .env.example .env
# Add your API keys to .env
docker compose up --build
```

Open: **http://localhost:3000**

---

## Extending the System

### Add a New Agent

```python
# backend/agents/my_agent/agent.py
def create_my_agent(llm_provider, session_path):
    return Agent(
        name="my_agent",
        llm_provider=llm_provider,
        instruction="Your custom prompt",
        tool_definitions=[...],
    )
```

### Add a New Tool

```python
# backend/tools/my_tool.py
def my_tool(param: str) -> str:
    """Tool description for LLM"""
    return f"Result: {param}"
```

### Add an LLM Provider

```python
# backend/core/llm_provider.py
class MyProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str:
        # Your implementation
        pass
```

---

## Configuration

```env
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-pro
```

---

## Project Structure

```
backend/
├── agents/           # Dialog & Coder agents
├── api/              # FastAPI routes
├── core/             # LLM, sessions, executor
└── tools/            # Agent tools

frontend/
├── src/components/   # React components
└── src/services/     # API client
```

Full technical documentation: [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)

---

## License

MIT
