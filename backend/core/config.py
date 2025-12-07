"""
Реализует модуль конфигурации моделей LLM.

Задачи:
- Загрузка `backend/models.json` как единого источника правды по моделям
- Учет переменных окружения `LLM_PROVIDER` и `LLM_MODEL` для выбора дефолтной модели
- Утилиты для получения информации о моделях
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


CONFIG_PATH = Path(__file__).resolve().parent.parent / "models.json"


class ModelsConfigError(RuntimeError):
  """Определяем ошибку конфигурации моделей (models.json)."""


@lru_cache(maxsize=1)
def load_models_config() -> Dict[str, Any]:
  """
  Загружаем и кэшируем конфиг моделей из models.json.
  :return: Словарь с ключами `providers` и `models`.
  """

  if not CONFIG_PATH.exists():
    raise ModelsConfigError(f"models.json not found at {CONFIG_PATH}")

  try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
      config = json.load(f)
  except Exception as e:  # pragma: no cover - защитный блок
    raise ModelsConfigError(f"Failed to load models config: {e}")

  providers = config.get("providers") or {}
  models = config.get("models") or []

  if not isinstance(providers, dict) or not isinstance(models, list):
    raise ModelsConfigError("Invalid models.json structure: expected 'providers' dict and 'models' list")

  # Применяем дефолт из env: LLM_PROVIDER / LLM_MODEL
  provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
  env_model_id = os.getenv("LLM_MODEL")

  # Сбрасываем is_default, чтобы не было конфликтов
  for m in models:
    if "is_default" in m:
      m["is_default"] = bool(m["is_default"])

  if env_model_id:
    found = False
    for m in models:
      if m.get("provider") == provider_type and m.get("id") == env_model_id:
        m["is_default"] = True
        found = True
      else:
        # Для текущего провайдера сбрасываем другие дефолты
        if m.get("provider") == provider_type:
          m["is_default"] = False

    if not found:
      logger.warning(
        "LLM_MODEL='%s' for provider '%s' not found in models.json; using file defaults",
        env_model_id,
        provider_type,
      )

  return config


def get_all_models() -> List[Dict[str, Any]]:
  """
  Возвращаем список всех моделей (как есть в конфиге).
  :return: список словарей моделей
  """

  config = load_models_config()
  return config.get("models", [])


def get_models_for_provider(provider: str) -> List[Dict[str, Any]]:
  """
  Возвращаем модели для конкретного провайдера.
  :param provider: имя провайдера
  :return: список моделей
  """

  provider = provider.lower()
  return [m for m in get_all_models() if m.get("provider", "").lower() == provider]


def get_model_by_id(model_id: str) -> Optional[Dict[str, Any]]:
  """
  Ищем модель по её id.
  :param model_id: ID модели
  :return: словарь модели или None
  """

  for m in get_all_models():
    if m.get("id") == model_id:
      return m
  return None


def get_default_model(provider: Optional[str] = None) -> Dict[str, Any]:
  """
  Получаем дефолтную модель.

  Выбираем по правилам:
  1) Если передан `provider` — работаем в его рамках, иначе берём `LLM_PROVIDER` из env (gemini/openrouter/...)
  2) Если `LLM_MODEL` указывает на модель данного провайдера и она есть в списке — используем её
  3) Иначе ищем в конфиге модель с `is_default=true` для этого провайдера
  4) Если нет is_default — берём первую модель данного провайдера
  5) Если и её нет — бросаем ModelsConfigError

  :param provider: опциональный провайдер
  :return: словарь модели
  """

  config = load_models_config()
  models = config.get("models", [])

  provider_type = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
  env_model_id = os.getenv("LLM_MODEL")

  # 2) Попробовать LLM_MODEL
  if env_model_id:
    for m in models:
      if m.get("provider", "").lower() == provider_type and m.get("id") == env_model_id:
        return m

  # 3) Ищем is_default
  for m in models:
    if m.get("provider", "").lower() == provider_type and m.get("is_default"):
      return m

  # 4) Первая модель провайдера
  for m in models:
    if m.get("provider", "").lower() == provider_type:
      return m

  raise ModelsConfigError(f"No models configured for provider '{provider_type}' in models.json")


def get_max_context_tokens(model_id: str) -> int:
  """
  Получаем максимальный размер контекста для модели.
  Если модель не найдена или поле отсутствует — возвращаем разумный дефолт (128k).
  :param model_id: ID модели
  :return: максимальное количество токенов
  """

  model = get_model_by_id(model_id)
  if not model:
    logger.warning("Model '%s' not found in models.json; using default context limit", model_id)
    return 128000

  try:
    value = int(model.get("max_context_tokens", 128000))
    return value
  except Exception:
    logger.warning("Invalid max_context_tokens for model '%s'; using default", model_id)
    return 128000