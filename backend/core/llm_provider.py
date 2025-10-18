"""Универсальный LLM-провайдер с поддержкой:
- Gemini (google-generativeai)
- OpenRouter (OpenAI-compatible API)

Фабрика умеет создавать провайдер по типу или по конфигурации модели
из ``backend/models.json`` (см. :mod:`backend.core.config`).
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any
import os
import logging

from . import config as models_config


logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Базовый класс для всех LLM провайдеров

    Также отвечает за базовый учёт токенов (usage) для провайдеров,
    чтобы backend мог агрегировать статистику по сессии.
    """

    def __init__(self) -> None:
        # Агрегированный usage по всем вызовам generate()/stream() за "ход"
        self._usage_totals: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        # Последний usage, возвращенный провайдером
        self._last_usage: Optional[Dict[str, int]] = None

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Синхронная генерация ответа"""
        pass
    
    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Потоковая генерация ответа"""
        pass

    # ===== Метрики токенов =====

    def reset_usage(self) -> None:
        """Сбросить счётчики usage перед новым ходом агента."""
        self._usage_totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._last_usage = None

    def _record_usage(self, usage: Optional[Dict[str, Any]]) -> None:
        """Внутренний метод для записи usage из конкретного LLM вызова.

        Ожидается словарь формата:
        {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        if not usage:
            return

        # Последний usage за один вызов
        self._last_usage = {
            k: int(v)
            for k, v in usage.items()
            if k in ("prompt_tokens", "completion_tokens", "total_tokens") and isinstance(v, (int, float))
        }

        # Агрегация по ходу
        for k, v in self._last_usage.items():
            self._usage_totals[k] = self._usage_totals.get(k, 0) + v

    def get_last_usage(self) -> Optional[Dict[str, int]]:
        """Вернуть usage последнего LLM-вызова (если провайдер его поддерживает)."""
        return dict(self._last_usage) if self._last_usage is not None else None

    def get_cumulative_usage(self) -> Dict[str, int]:
        """Суммарный usage по всем вызовам с момента последнего reset_usage()."""
        return dict(self._usage_totals)
    
    def get_context_limit(self) -> int:
        """
        Получить лимит контекста в токенах
        
        Returns:
            Примерный лимит токенов для модели
        """
        return getattr(self, '_context_limit', 128000)  # Default 128K tokens
    
    def estimate_tokens(self, text: str) -> int:
        """
        Оценить количество токенов в тексте
        
        Простая эвристика: ~4 символа = 1 токен для английского
        ~2-3 символа = 1 токен для русского (больше multi-byte chars)
        
        Args:
            text: Текст для оценки
        
        Returns:
            Примерное количество токенов
        """
        # Простая эвристика: среднее между английским и русским
        return len(text) // 3
    
    def calculate_available_space(self, 
                                  system_prompt: str = "",
                                  history: str = "",
                                  buffer_ratio: float = 0.2) -> int:
        """
        Рассчитать доступное место для контента
        
        Args:
            system_prompt: Системный промпт
            history: История сообщений
            buffer_ratio: Процент для буфера (response space)
        
        Returns:
            Количество символов доступных для контента
        """
        total_limit = self.get_context_limit()
        
        # Оценить уже использованные токены
        used_tokens = self.estimate_tokens(system_prompt) + self.estimate_tokens(history)
        
        # Оставить buffer для ответа (20% по умолчанию)
        buffer_tokens = int(total_limit * buffer_ratio)
        
        # Доступные токены
        available_tokens = total_limit - used_tokens - buffer_tokens
        
        # Конвертировать обратно в символы (с запасом)
        available_chars = max(0, available_tokens * 3)  # Conservative estimate
        
        return available_chars


class GeminiProvider(BaseLLMProvider):
    """Google Gemini через google-generativeai SDK"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        super().__init__()
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model
        
        # Установить лимит контекста в зависимости от модели
        if "2.5" in model or "2.0" in model or "1.5" in model:
            self._context_limit = 2000000  # 2M tokens для новых Gemini
        else:
            self._context_limit = 1000000  # 1M tokens для старых
    
    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get('temperature', 0.7)
        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": temperature}
        )
        # usage_metadata доступен в SDK google-generativeai и содержит
        # prompt_token_count, candidates_token_count, total_token_count
        usage = getattr(response, "usage_metadata", None)
        usage_dict = None
        if usage is not None:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "completion_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        self._record_usage(usage_dict)
        return response.text
    
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        temperature = kwargs.get('temperature', 0.7)
        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": temperature},
            stream=True
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    
    def generate_with_search(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Генерация с Grounding Search (встроенный поиск Google)
        
        Использует google_search_retrieval для получения актуальной информации.
        Лимиты Free Tier: зависят от модели
        Лимиты Paid Tier: 1,500/day бесплатно, затем $35/1000
        
        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с response и grounding_metadata (источники)
        """
        import google.generativeai as genai
        
        temperature = kwargs.get('temperature', 0.7)
        
        # Создаём модель с grounding tool
        # google_search_retrieval включает встроенный поиск
        grounding_tool = genai.Tool(
            google_search_retrieval=genai.GoogleSearchRetrieval()
        )
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": temperature},
                tools=[grounding_tool]
            )
            
            # Извлекаем usage
            usage = getattr(response, "usage_metadata", None)
            usage_dict = None
            if usage is not None:
                usage_dict = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", None),
                    "completion_tokens": getattr(usage, "candidates_token_count", None),
                    "total_tokens": getattr(usage, "total_token_count", None),
                }
            self._record_usage(usage_dict)
            
            # Извлекаем grounding metadata (источники)
            grounding_metadata = None
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata'):
                    gm = candidate.grounding_metadata
                    grounding_metadata = {
                        "search_entry_point": getattr(gm, 'search_entry_point', None),
                        "grounding_chunks": [],
                        "web_search_queries": getattr(gm, 'web_search_queries', []),
                    }
                    
                    # Парсим grounding chunks (источники)
                    if hasattr(gm, 'grounding_chunks'):
                        for chunk in gm.grounding_chunks:
                            if hasattr(chunk, 'web'):
                                grounding_metadata["grounding_chunks"].append({
                                    "uri": chunk.web.uri if hasattr(chunk.web, 'uri') else None,
                                    "title": chunk.web.title if hasattr(chunk.web, 'title') else None,
                                })
            
            return {
                "response": response.text,
                "grounding_metadata": grounding_metadata,
                "usage": usage_dict
            }
            
        except Exception as e:
            logger.warning(f"Grounding search failed, falling back to regular generate: {e}")
            # Fallback на обычную генерацию
            return {
                "response": self.generate(prompt, **kwargs),
                "grounding_metadata": None,
                "usage": self._last_usage
            }


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter (OpenAI-compatible API)"""
    
    def __init__(self, api_key: str, model: str):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Установить лимит контекста в зависимости от модели
        model_limits = {
            "gpt-4": 128000,
            "gpt-4-turbo": 128000,
            "gpt-3.5": 16000,
            "claude-3": 200000,
            "claude-3.5": 200000,
        }
        
        # Найти лимит по частичному совпадению названия модели
        self._context_limit = 128000  # Default
        for key, limit in model_limits.items():
            if key in model.lower():
                self._context_limit = limit
                break
    
    def generate(self, prompt: str, **kwargs) -> str:
        import requests

        temperature = kwargs.get('temperature', 0.7)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
        )
        response.raise_for_status()
        data = response.json()

        # usage: {"prompt_tokens", "completion_tokens", "total_tokens", ...}
        usage = data.get("usage") or {}
        usage_dict = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        self._record_usage(usage_dict)

        return data["choices"][0]["message"]["content"]
    
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        import requests
        import json

        temperature = kwargs.get('temperature', 0.7)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": True
            },
            stream=True
        )
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        pass


def get_llm_provider(provider_type: str, **config) -> BaseLLMProvider:
    """Фабрика LLM-провайдеров по явному типу.

    Пример использования::

        llm = get_llm_provider("gemini", api_key="...", model="gemini-2.5-pro")
        response = llm.generate("Hello, how are you?")

    Этот уровень по-прежнему поддерживается для обратной совместимости.
    Для конфигурации через models.json предпочтителен
    :func:`get_llm_provider_for_model`.
    """

    providers = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        # "anthropic": ClaudeProvider,  # TODO: добавить позже
        # "openai": OpenAIProvider,      # TODO: добавить позже
    }

    if provider_type not in providers:
        raise ValueError(f"Unknown provider: {provider_type}. Available: {list(providers.keys())}")

    return providers[provider_type](**config)


def get_llm_provider_for_model(model_id: Optional[str] = None) -> BaseLLMProvider:
    """Создать LLM-провайдер на основе конфигурации модели.

    Логика:
    1) Если `model_id` передан — берём модель из models.json по id
    2) Иначе — берём дефолтную модель через config.get_default_model()
    3) По полю `provider` выбираем тип провайдера (gemini/openrouter/...)
    4) API-ключ берём из соответствующей переменной окружения
    5) При наличии max_context_tokens переопределяем лимит контекста у провайдера
    """

    if model_id is None:
        model_cfg = models_config.get_default_model()
    else:
        model_cfg = models_config.get_model_by_id(model_id)
        if model_cfg is None:
            raise ValueError(f"Model '{model_id}' not found in models.json")

    provider_type = (model_cfg.get("provider") or "").lower()
    model_identifier = model_cfg.get("id")

    api_env_by_provider = {
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "sherlock": "SHERLOCK_API_KEY",
    }

    if provider_type not in api_env_by_provider:
        raise ValueError(f"Unsupported provider '{provider_type}' for model '{model_identifier}'")

    api_env = api_env_by_provider[provider_type]
    api_key = os.getenv(api_env)
    if not api_key:
        raise ValueError(
            f"API key for provider '{provider_type}' not configured. "
            f"Expected environment variable {api_env}."
        )

    llm = get_llm_provider(provider_type, api_key=api_key, model=model_identifier)

    # Переопределить лимит контекста из конфигурации модели, если он задан
    max_ctx = model_cfg.get("max_context_tokens")
    if isinstance(max_ctx, int) and max_ctx > 0:
        setattr(llm, "_context_limit", max_ctx)

    logger.info("Initialized LLM provider '%s' with model '%s' (context=%s)",
                provider_type, model_identifier, getattr(llm, "_context_limit", None))

    return llm
