# 🤖 Multi-Agent AI Router

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6.svg)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Modular AI agent platform with multi-provider LLM support.**

> 📚 *This is a demo project for learning and exploration purposes.*

🇷🇺 [Русская версия](README_RU.md)

---

## 🎯 What Makes It Cool

| Feature | Description |
|---------|-------------|
| **🔌 Plug & Play LLMs** | Switch between Gemini, OpenRouter, or any OpenAI-compatible API |
| **🧩 Modular Agents** | Each agent is independent — add your own in minutes |
| **🛠️ Real Tool Execution** | Agents don't just chat — they *do* things: search, code, analyze |
| **📊 Live Crypto Data** | Binance API integration with real-time prices, orderbook, trades |
| **🐳 Docker Sandbox** | Code execution in isolated containers — safe and reproducible |
| **⚡ Native Tool Calling** | Gemini 2.5 Pro uses native function calling for reliable execution |

---

## 🤖 Agents

### 🔍 Dialog Agent
*Intelligent conversational agent with web capabilities*

- **Smart Search** — Multi-source web search with result aggregation
- **Page Reading** — Extract and summarize content from any URL
- **Context Awareness** — Maintains conversation history and session state

---

### 🧠 Coder Agent
*Full-featured coding assistant that actually executes code*

![Coder Agent](coder_screen.png)

- **File Operations** — Create, read, list files in isolated workspace
- **Code Execution** — Run Python in sandboxed Docker environment
- **Multi-File Projects** — Import between files, build complete projects
- **Native Tool Calling** — Gemini 2.5 Pro uses native function calling

**Example:**
```
User: Calculate fibonacci sequence up to 100

Agent: I'll create and run a Python script for you.
[Creates fibonacci.py → Executes → Returns result]

Output: [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
```


---

### 📊 Crypto Analyst Agent
*Professional cryptocurrency analyzer with real-time Binance data*

![Crypto Analyst](crypto_screen.png)

**Real-time data from Binance API:**
- 💰 **Price & Candles** — Current price, 24h change, multi-timeframe data
- 📈 **Technical Indicators** — RSI, MACD, EMA on 5m/1h/4h/1d timeframes
- 📊 **Orderbook Analysis** — Deltas at 1.5%, 5%, 15%, 60% from price
- 🔄 **Trade Flow** — Buy/sell pressure, whale activity detection
- 😨 **Market Context** — Fear & Greed Index, total market cap

**Example Output:**
```
📊 BTC/USDT Analysis | 2025-12-07

💰 Price: $88,993.33 (-0.80% 24h)
📈 Trend: Bearish (3/4 timeframes)

Technical:
- RSI 1h: 40.15 (neutral-weak)
- MACD: bearish on 1h/4h/1d

Orderbook Deltas:
- 1.5%: Bid=85.99, Ask=81.22, 🟢 buy pressure
- 5%:   Bid=85.99, Ask=81.22, 🟢 buy pressure

Trade Flow:
- Buy: 259 trades, Sell: 741 trades
- Volume ratio: 10.2% buy
- Whale direction: sell

😨 Fear & Greed: 20 (Extreme Fear)
🔑 Support: $88,900 | Resistance: $89,100
```

---

## 🏗️ Architecture

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

## 🔐 Security

This project implements multiple layers of security for code execution:

| Layer | Protection |
|-------|------------|
| **🐳 Sandbox Container** | Code runs in isolated Docker container with no network access |
| **📁 Path Validation** | All file operations restricted to session workspace |
| **⏱️ Resource Limits** | CPU, memory, and timeout constraints |
| **👤 Non-root User** | Sandbox runs as unprivileged user |

> ⚠️ **Disclaimer**: This is a demonstration project. For production use, consider additional hardening (gVisor, Firecracker, etc.)

---

## 🚀 Quick Start

```bash
git clone https://github.com/nssanta/Multi-Agent-Router.git
cd Multi-Agent-Router
cp .env.example .env
# Add your API keys to .env
docker compose up --build
```

Open: **http://localhost:3000**

---

## ⚙️ Configuration

```env
# Required
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional
LLM_PROVIDER=gemini          # or openrouter
LLM_MODEL=gemini-2.5-pro     # default model
```

---

## 🔧 Extending the System

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

---

## 📁 Project Structure

```
backend/
├── agents/           # Dialog, Coder, Crypto agents
│   ├── dialog/       # Conversational agent
│   ├── coder/        # Code execution agent
│   └── crypto/       # Cryptocurrency analyst
├── api/              # FastAPI routes
├── core/             # LLM providers, sessions, executor
└── tools/            # Agent tools
    ├── web/          # Search, page reader
    └── crypto/       # Binance API, indicators

frontend/
├── src/components/   # React components
└── src/services/     # API client
```

Full technical documentation: [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)

---

## 📄 License

MIT
