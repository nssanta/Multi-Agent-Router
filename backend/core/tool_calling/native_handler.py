"""
Native Tool Handler

Обработка native tool calling через API провайдеров.
Поддерживает OpenAI-совместимый формат (OpenRouter, OpenAI, Azure, и т.д.)
и Gemini native function calling.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .base import ToolCall, ToolCallBatch, ToolCallSource

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """
    Определение инструмента для API
    
    Используется для генерации JSON Schema в формате OpenAI/OpenRouter.
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str] = None
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Формат для OpenAI/OpenRouter API"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required or []
                }
            }
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """Формат для Gemini API"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": self._convert_types_to_gemini(self.parameters),
                "required": self.required or []
            }
        }
    
    def _convert_types_to_gemini(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертация типов в Gemini формат (STRING, NUMBER, etc.)"""
        converted = {}
        type_map = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT"
        }
        
        for key, value in props.items():
            new_value = value.copy()
            if "type" in new_value:
                new_value["type"] = type_map.get(new_value["type"], new_value["type"].upper())
            converted[key] = new_value
        
        return converted


class NativeToolHandler:
    """
    Обработчик native tool calling
    
    Отвечает за:
    1. Подготовку tool definitions для API
    2. Парсинг tool_calls из ответа API
    3. Формирование messages для multi-turn
    
    Пример использования:
        handler = NativeToolHandler()
        handler.add_tool(write_file_definition)
        handler.add_tool(read_file_definition)
        
        # Отправка запроса
        request_body = handler.prepare_request(messages)
        response = llm_provider.generate_with_tools(request_body)
        
        # Парсинг ответа
        tool_calls = handler.parse_response(response)
    """
    
    def __init__(self):
        self.tools: List[ToolDefinition] = []
        self._tool_choice: str = "auto"  # auto, none, required, или конкретный tool
    
    def add_tool(self, tool: ToolDefinition) -> None:
        """Добавить определение инструмента"""
        self.tools.append(tool)
    
    def add_tools_from_registry(self, agent_type: str = "coder") -> None:
        """
        Добавить инструменты из глобального реестра
        
        Args:
            agent_type: Тип агента для фильтрации инструментов
        """
        from backend.tools import tool_registry
        
        schemas = tool_registry.get_schemas_for_agent(agent_type)
        for schema in schemas:
            self.tools.append(ToolDefinition(
                name=schema["name"],
                description=schema["description"],
                parameters=schema["parameters"].get("properties", {}),
                required=schema["parameters"].get("required", [])
            ))
    
    def set_tool_choice(self, choice: str) -> None:
        """
        Установить стратегию выбора инструментов
        
        Args:
            choice: "auto", "none", "required", или имя конкретного tool
        """
        self._tool_choice = choice
    
    def get_tools_for_request(self, format: str = "openai") -> List[Dict[str, Any]]:
        """
        Получить список tools для API запроса
        
        Args:
            format: "openai" или "gemini"
            
        Returns:
            Список tool definitions в нужном формате
        """
        if format == "gemini":
            return [t.to_gemini_format() for t in self.tools]
        else:
            return [t.to_openai_format() for t in self.tools]
    
    def get_tool_choice_for_request(self, format: str = "openai") -> Any:
        """
        Получить tool_choice параметр для запроса
        """
        if self._tool_choice in ["auto", "none", "required"]:
            return self._tool_choice
        else:
            # Конкретный инструмент
            if format == "openai":
                return {
                    "type": "function",
                    "function": {"name": self._tool_choice}
                }
            else:
                return self._tool_choice  # Gemini использует просто имя
    
    def prepare_request_params(self, format: str = "openai") -> Dict[str, Any]:
        """
        Подготовить параметры для API запроса
        
        Returns:
            Dict с tools и tool_choice
        """
        return {
            "tools": self.get_tools_for_request(format),
            "tool_choice": self.get_tool_choice_for_request(format)
        }
    
    def parse_response(self, response: Dict[str, Any]) -> ToolCallBatch:
        """
        Парсинг ответа API с tool_calls
        
        Args:
            response: Ответ от API (OpenAI/OpenRouter формат)
            
        Returns:
            ToolCallBatch с извлечёнными вызовами
        """
        batch = ToolCallBatch()
        
        # OpenAI/OpenRouter формат
        choices = response.get("choices", [])
        if not choices:
            return batch
        
        message = choices[0].get("message", {})
        tool_calls_raw = message.get("tool_calls", [])
        
        for tc in tool_calls_raw:
            try:
                call = ToolCall.from_openai_format(tc)
                batch.add(call)
            except Exception as e:
                logger.warning(f"Failed to parse tool_call: {e}")
                continue
        
        return batch
    
    def parse_gemini_response(self, response: Any) -> ToolCallBatch:
        """
        Парсинг ответа Gemini API
        
        Args:
            response: GenerateContentResponse от Gemini
            
        Returns:
            ToolCallBatch с извлечёнными вызовами
        """
        batch = ToolCallBatch()
        
        try:
            # Gemini возвращает function_calls в candidates
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            fc = part.function_call
                            
                            # Извлекаем аргументы
                            args = {}
                            if hasattr(fc, 'args'):
                                args = dict(fc.args)
                            
                            call = ToolCall(
                                name=fc.name,
                                arguments=args,
                                source=ToolCallSource.NATIVE
                            )
                            batch.add(call)
        
        except Exception as e:
            logger.warning(f"Failed to parse Gemini response: {e}")
        
        return batch
    
    def format_results_for_llm(self, batch: ToolCallBatch) -> List[Dict[str, Any]]:
        """
        Форматировать результаты для отправки обратно в LLM
        
        Args:
            batch: ToolCallBatch с результатами
            
        Returns:
            Список messages для добавления в conversation
        """
        messages = []
        
        # 1. Assistant message с tool_calls
        if batch.calls:
            messages.append(batch.to_assistant_message())
        
        # 2. Tool messages с результатами
        messages.extend(batch.to_tool_messages())
        
        return messages


# === Предопределённые Tool Definitions ===

# Инструменты для Coder Agent
CODER_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="write_file",
        description="Записать содержимое в файл. Создаёт файл если не существует, перезаписывает если существует.",
        parameters={
            "path": {
                "type": "string",
                "description": "Путь к файлу (относительно workspace сессии)"
            },
            "content": {
                "type": "string",
                "description": "Содержимое для записи"
            }
        },
        required=["path", "content"]
    ),
    ToolDefinition(
        name="read_file",
        description="Прочитать содержимое файла",
        parameters={
            "path": {
                "type": "string",
                "description": "Путь к файлу"
            },
            "start_line": {
                "type": "integer",
                "description": "Начальная строка (опционально, 1-indexed)"
            },
            "end_line": {
                "type": "integer",
                "description": "Конечная строка (опционально)"
            }
        },
        required=["path"]
    ),
    ToolDefinition(
        name="list_directory",
        description="Получить список файлов и папок в директории",
        parameters={
            "path": {
                "type": "string",
                "description": "Путь к директории"
            },
            "recursive": {
                "type": "boolean",
                "description": "Рекурсивный обход (по умолчанию false)"
            }
        },
        required=["path"]
    ),
    ToolDefinition(
        name="run_code",
        description="Выполнить код Python в изолированной среде",
        parameters={
            "code": {
                "type": "string",
                "description": "Python код для выполнения"
            },
            "timeout": {
                "type": "integer",
                "description": "Таймаут в секундах (по умолчанию 30)"
            }
        },
        required=["code"]
    ),
    ToolDefinition(
        name="search_files",
        description="Поиск по содержимому файлов",
        parameters={
            "pattern": {
                "type": "string",
                "description": "Паттерн для поиска (regex или текст)"
            },
            "path": {
                "type": "string",
                "description": "Директория для поиска"
            },
            "file_pattern": {
                "type": "string",
                "description": "Фильтр по имени файла (glob pattern, например *.py)"
            }
        },
        required=["pattern"]
    ),
]


def get_coder_tools() -> List[ToolDefinition]:
    """Получить все tool definitions для Coder Agent"""
    return CODER_TOOL_DEFINITIONS.copy()


def create_handler_for_coder() -> NativeToolHandler:
    """Создать настроенный handler для Coder Agent"""
    handler = NativeToolHandler()
    for tool in CODER_TOOL_DEFINITIONS:
        handler.add_tool(tool)
    return handler
