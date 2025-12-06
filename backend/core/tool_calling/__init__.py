"""
Universal Tool Calling System

Двухуровневая система для работы с инструментами:
1. Native Tool Calling - через API провайдера (OpenRouter, OpenAI, и т.д.)
2. Text Fallback - парсинг из текстового ответа LLM

Поддерживает любые LLM модели через:
- OpenAI-совместимый API (OpenRouter унифицирует 100+ моделей)
- Gemini native function calling
- Text-based fallback для legacy моделей
"""

from .base import (
    ToolCall,
    ToolCallSource,
    ToolExecutionResult,
    ToolCallBatch,
)
from .text_extractor import ToolCallExtractor
from .executor import ToolExecutor
from .native_handler import NativeToolHandler

__all__ = [
    # Базовые типы
    'ToolCall',
    'ToolCallSource', 
    'ToolExecutionResult',
    'ToolCallBatch',
    # Компоненты
    'ToolCallExtractor',
    'ToolExecutor',
    'NativeToolHandler',
]
