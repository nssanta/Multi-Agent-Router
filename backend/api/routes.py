"""REST API endpoints"""

from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import shutil
import os
from fastapi.middleware.cors import CORSMiddleware

from backend.core.session import SessionManager
from backend.core.llm_provider import get_llm_provider_for_model
from backend.core import config as models_config
from backend.agents.dialog.agent import create_dialog_agent
from backend.agents.coder.agent import create_coder_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для разработки, в продакшене лучше указать конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные объекты
session_manager = SessionManager()


class ChatRequest(BaseModel):
    session_id: str
    agent_type: str
    message: str
    search_enabled: bool = True

class CreateSessionRequest(BaseModel):
    agent_type: str
    user_id: str = "default"
    model_id: Optional[str] = None


@app.on_event("startup")
def startup():
    """Инициализация при старте"""

    # Создать рабочую директорию, если ее нет
    Path("./workspace/sessions").mkdir(parents=True, exist_ok=True)

    # Загрузить конфиг моделей и убедиться, что дефолтная модель существует
    try:
        config = models_config.load_models_config()
    except Exception as e:  # pragma: no cover - фатальная ошибка конфигурации
        raise RuntimeError(f"Failed to load models config: {e}")

    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Проверить наличие дефолтной модели (учитывает LLM_MODEL, если указана)
    try:
        default_model = models_config.get_default_model(provider_type)
    except Exception as e:
        raise RuntimeError(f"Failed to determine default model for provider '{provider_type}': {e}")

    # Проверить, что для дефолтного провайдера есть API-ключ
    api_env_by_provider = {
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "sherlock": "SHERLOCK_API_KEY",
    }

    api_env = api_env_by_provider.get(provider_type)
    if not api_env:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {provider_type}. "
            f"Supported: {list(api_env_by_provider.keys())}"
        )

    api_key = os.getenv(api_env)
    if not api_key:
        raise RuntimeError(
            f"API key not found for provider {provider_type}. "
            f"Set {api_env} accordingly."
        )

    print(
        f"✅ Initialized model config: provider={provider_type}, "
        f"default_model_id={default_model.get('id')}"
    )


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest):
    """Создать новую сессию"""
    # Если модель не указана явно, взять дефолт для текущего провайдера
    model_id = req.model_id
    if not model_id:
        default_model = models_config.get_default_model()
        model_id = default_model.get("id")

    session = session_manager.create_session(
        agent_type=req.agent_type,
        user_id=req.user_id,
        model_id=model_id,
    )
    return session


@app.get("/api/sessions")
def list_sessions(agent_type: str = None):
    """Список всех сессий"""
    sessions = session_manager.list_sessions(agent_type)
    return {"sessions": sessions}


@app.get("/api/sessions/{agent_type}/{session_id}")
def get_session(agent_type: str, session_id: str):
    """Получить сессию по ID"""
    session = session_manager.get_session(session_id, agent_type)
    return session


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Отправить сообщение агенту"""
    
    # Получить session path и историю
    try:
        session = session_manager.get_session(req.session_id, req.agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    session_path = Path(session["path"])

    # Получить историю сообщений (для контекста)
    history = session.get("messages", [])

    # Определить модель для этой сессии
    session_state = session.get("state", {})
    model_id = session_state.get("model_id")
    if not model_id:
        # Если старая сессия без модели – привязать к дефолтной
        default_model = models_config.get_default_model()
        model_id = default_model.get("id")
        session_manager.update_state(req.session_id, req.agent_type, {"model_id": model_id})

    # Обновить search_enabled в state сессии
    session_manager.update_state(
        req.session_id,
        req.agent_type,
        {"search_enabled": req.search_enabled},
    )

    # Создать LLM-провайдера исходя из выбранной модели
    try:
        llm_provider = get_llm_provider_for_model(model_id)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Сбросить usage перед новым ходом (если провайдер поддерживает учёт токенов)
    reset_usage = getattr(llm_provider, "reset_usage", None)
    if callable(reset_usage):
        reset_usage()

    # Создать агента
    if req.agent_type == "dialog":
        agent = create_dialog_agent(llm_provider, session_path)
    elif req.agent_type == "coder":
        # Получаем настройки из state
        coder_config = session_state.get("coder_config", {})
        agent = create_coder_agent(
            llm_provider,
            session_path,
            use_tree_of_thoughts=coder_config.get("use_tree_of_thoughts", True),
            num_branches=coder_config.get("num_branches", 2),
            use_verifier=coder_config.get("use_verifier", True),
            verifier_model_id=coder_config.get("verifier_model_id"),
        )
    else:
        raise HTTPException(400, f"Agent type {req.agent_type} not implemented yet")

    # Загрузить state из сессии в агента (search_enabled, модель и т.п.)
    session = session_manager.get_session(req.session_id, req.agent_type)
    session_state = session.get("state", {})
    agent.state.data.update(session_state)
    
    # Запустить агента С ИСТОРИЕЙ и СТРИМИНГОМ
    import json
    
    async def event_generator():
        # 1. Stream agent events
        full_response = ""
        try:
            for event in agent.run_stream(req.message, history=history):
                # Aggregate text for history saving
                if event["type"] == "token":
                    full_response += event["content"]
                
                # Yield SSE event
                yield f"data: {json.dumps(event)}\n\n"
                
                # Handle system events (Tool Outputs)
                if event["type"] == "system":
                     session_manager.add_message(req.session_id, req.agent_type, "system", event["content"])
                     
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        # 2. Finalize & Save History
        session_manager.add_message(req.session_id, req.agent_type, "user", req.message)
        if full_response.strip():
            session_manager.add_message(req.session_id, req.agent_type, "assistant", full_response)
        
        # 3. Calculate Usage
        cumulative_usage = {}
        get_usage = getattr(llm_provider, "get_cumulative_usage", None)
        if callable(get_usage):
            try:
                cumulative_usage = get_usage() or {}
            except Exception:
                pass

        prev_usage = session_state.get("usage") or {}
        last_p = int(cumulative_usage.get("prompt_tokens") or 0)
        last_c = int(cumulative_usage.get("completion_tokens") or 0)
        last_t = int(cumulative_usage.get("total_tokens") or (last_p + last_c))
        
        sp = int(prev_usage.get("session_prompt_tokens", 0)) + last_p
        sc = int(prev_usage.get("session_completion_tokens", 0)) + last_c
        st = int(prev_usage.get("session_total_tokens", 0)) + last_t
        
        new_usage = {
            "session_prompt_tokens": sp,
            "session_completion_tokens": sc,
            "session_total_tokens": st,
            "context_usage_percent": 0.0 # Simplified for stream
        }
        
        session_manager.update_state(
            req.session_id,
            req.agent_type,
            {
                "model_id": model_id,
                "usage": new_usage,
            },
        )
        
        # Yield usage event
        yield f"data: {json.dumps({'type': 'usage', 'content': new_usage})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/models")
def list_models(provider: Optional[str] = None):
    """Список доступных LLM-моделей.

    Если передан параметр `provider`, список фильтруется по нему
    (например, `provider=openrouter`).
    """

    if provider:
        models = models_config.get_models_for_provider(provider)
    else:
        models = models_config.get_all_models()

    return {"models": models}


@app.get("/api/models/openrouter-free")
async def get_openrouter_free_models():
    """
    Динамически получить список бесплатных моделей от OpenRouter API.
    
    Фильтрует модели где pricing.prompt = "0" и pricing.completion = "0".
    Кеширует результат на 1 час.
    """
    import requests
    import time
    
    # Простой кеш в памяти
    cache_key = "_openrouter_free_cache"
    cache_time_key = "_openrouter_free_cache_time"
    cache_ttl = 3600  # 1 час
    
    # Проверяем кеш
    cached = getattr(get_openrouter_free_models, cache_key, None)
    cached_time = getattr(get_openrouter_free_models, cache_time_key, 0)
    
    if cached and (time.time() - cached_time) < cache_ttl:
        return {"models": cached, "cached": True}
    
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        free_models = []
        for model in data.get("data", []):
            pricing = model.get("pricing", {})
            # Free models have "0" pricing for both prompt and completion
            if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                free_models.append({
                    "id": model.get("id"),
                    "display_name": model.get("name", model.get("id")),
                    "provider": "openrouter",
                    "max_context_tokens": model.get("context_length", 4096),
                    "tags": ["free", "dynamic"],
                    "description": model.get("description", ""),
                })
        
        # Сортируем по имени
        free_models.sort(key=lambda x: x.get("display_name", ""))
        
        # Кешируем
        setattr(get_openrouter_free_models, cache_key, free_models)
        setattr(get_openrouter_free_models, cache_time_key, time.time())
        
        return {"models": free_models, "cached": False, "count": len(free_models)}
        
    except Exception as e:
        # В случае ошибки возвращаем пустой список
        return {"models": [], "error": str(e), "cached": False}


@app.post("/api/upload/{agent_type}/{session_id}")
async def upload_file(agent_type: str, session_id: str, file: UploadFile = File(...)):
    """Загрузить файл в сессию"""
    
    try:
        session = session_manager.get_session(session_id, agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    session_path = Path(session["path"])
    
    # Сохранить файл в input/
    file_path = session_path / "input" / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {"filename": file.filename, "path": str(file_path)}


@app.delete("/api/sessions/{agent_type}/{session_id}")
def delete_session(agent_type: str, session_id: str):
    """Удалить сессию"""
    try:
        session_manager.delete_session(session_id, agent_type)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{agent_type}/{session_id}/files")
def list_session_files(agent_type: str, session_id: str):
    """Получить список файлов в сессии"""
    try:
        session = session_manager.get_session(session_id, agent_type)
        session_path = Path(session["path"])
        
        # Получить файлы из input/ и workspace/
        input_files = []
        workspace_files = []
        
        input_dir = session_path / "input"
        if input_dir.exists():
            for file in input_dir.iterdir():
                if file.is_file():
                    input_files.append({
                        "name": file.name,
                        "size": file.stat().st_size,
                        "modified": file.stat().st_mtime,
                        "path": str(file.relative_to(session_path))
                    })
        
        workspace_dir = session_path / "workspace"
        if workspace_dir.exists():
            for file in workspace_dir.rglob("*"):
                if file.is_file():
                    workspace_files.append({
                        "name": file.name,
                        "size": file.stat().st_size,
                        "modified": file.stat().st_mtime,
                        "path": str(file.relative_to(session_path))
                    })
        
        return {
            "session_id": session_id,
            "input_files": input_files,
            "workspace_files": workspace_files
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/sessions/{agent_type}/{session_id}/logs")
def get_session_logs(agent_type: str, session_id: str):
    """Получить логи сессии"""
    try:
        session = session_manager.get_session(session_id, agent_type)
        session_path = Path(session["path"])
        logs_dir = session_path / "logs"
        
        if not logs_dir.exists():
            return {"logs": []}
        
        logs = []
        for log_file in sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
            import json
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                    logs.append({
                        "filename": log_file.name,
                        "timestamp": log_data.get("timestamp"),
                        "type": "agent" if "agent" in log_file.name else "code_exec",
                        "data": log_data
                    })
            except:
                # Skip invalid log files
                pass
        
        return {"session_id": session_id, "logs": logs}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/agents")
def list_agents():
    """Список доступных агентов"""
    return {
        "agents": [
            {"id": "dialog", "name": "Dialog", "description": "Chat assistant with web search"},
            {"id": "coder", "name": "Coder", "description": "AI programming assistant with Tree of Thoughts"},
            {"id": "mle", "name": "MLE", "description": "Machine Learning Engineering (Coming soon)"},
            {"id": "ds", "name": "DS", "description": "Data Science (Coming soon)"}
        ]
    }