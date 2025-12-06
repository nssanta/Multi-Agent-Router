"""
Базовые типы для системы Tool Calling

Включает:
- ToolCall: представление вызова инструмента
- ToolCallSource: источник вызова (native API или текстовый парсинг)
- ToolExecutionResult: результат выполнения
- ToolCallBatch: группа вызовов для параллельного выполнения
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid
import json


class ToolCallSource(str, Enum):
    """Источник вызова инструмента"""
    NATIVE = "native"           # Через API tool_calls (структурированный)
    TEXT_PARSED = "text_parsed" # Извлечено из текста ответа
    MANUAL = "manual"           # Вручную созданный вызов


@dataclass
class ToolCall:
    """
    Представление вызова инструмента
    
    Унифицированный формат для всех источников:
    - Native API tool_calls
    - Извлечённые из текста
    - Созданные программно
    
    Attributes:
        id: Уникальный идентификатор вызова
        name: Имя инструмента (write_file, read_file, и т.д.)
        arguments: Аргументы в виде словаря
        source: Откуда получен вызов
        raw_text: Исходный текст (для TEXT_PARSED)
    """
    
    name: str
    arguments: Dict[str, Any]
    source: ToolCallSource = ToolCallSource.NATIVE
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    raw_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "source": self.source.value,
        }
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Формат для отправки как assistant message tool_calls"""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False)
            }
        }
    
    @classmethod
    def from_openai_format(cls, data: Dict[str, Any]) -> "ToolCall":
        """Создать из OpenAI/OpenRouter формата ответа"""
        func = data.get("function", {})
        
        # Парсим arguments из JSON строки
        args_raw = func.get("arguments", "{}")
        try:
            if isinstance(args_raw, str):
                arguments = json.loads(args_raw)
            else:
                arguments = args_raw
        except json.JSONDecodeError:
            arguments = {"raw": args_raw}
        
        return cls(
            id=data.get("id", f"call_{uuid.uuid4().hex[:12]}"),
            name=func.get("name", "unknown"),
            arguments=arguments,
            source=ToolCallSource.NATIVE
        )
    
    def __repr__(self) -> str:
        args_preview = str(self.arguments)[:50] + "..." if len(str(self.arguments)) > 50 else str(self.arguments)
        return f"<ToolCall {self.name}({args_preview}) source={self.source.value}>"


@dataclass
class ToolExecutionResult:
    """
    Результат выполнения инструмента
    
    Attributes:
        tool_call_id: ID соответствующего ToolCall
        tool_name: Имя инструмента
        success: Успешно ли выполнение
        data: Результат выполнения (любой тип)
        error: Сообщение об ошибке (если success=False)
        execution_time_ms: Время выполнения в миллисекундах
    """
    
    tool_call_id: str
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms
        }
    
    def to_message(self) -> Dict[str, Any]:
        """
        Формат для отправки как tool message обратно в LLM
        """
        content = self.data if self.success else f"Error: {self.error}"
        
        # Если data - словарь или список, сериализуем в JSON
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        elif content is None:
            content = "Success" if self.success else "Unknown error"
        else:
            content = str(content)
        
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.tool_name,
            "content": content
        }
    
    @classmethod
    def from_tool_result(cls, tool_call: ToolCall, result: Any, execution_time_ms: float = None) -> "ToolExecutionResult":
        """
        Создать из результата выполнения BaseTool
        
        Args:
            tool_call: Исходный ToolCall
            result: ToolResult от BaseTool.execute()
            execution_time_ms: Время выполнения
        """
        # Импортируем здесь чтобы избежать circular import
        from backend.tools.base import ToolResult as BaseToolResult
        
        if isinstance(result, BaseToolResult):
            return cls(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                success=result.is_success(),
                data=result.data if result.is_success() else None,
                error=result.error,
                execution_time_ms=execution_time_ms
            )
        else:
            # Fallback для других типов результатов
            return cls(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                success=True,
                data=result,
                execution_time_ms=execution_time_ms
            )
    
    def __repr__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"<ToolExecutionResult {status} {self.tool_name}>"


@dataclass 
class ToolCallBatch:
    """
    Группа вызовов инструментов
    
    Используется для:
    - Параллельных вызовов (parallel tool calls)
    - Группировки результатов
    - Multi-turn conversations
    
    Attributes:
        calls: Список вызовов
        results: Результаты выполнения (после execute)
        is_executed: Были ли вызовы выполнены
    """
    
    calls: List[ToolCall] = field(default_factory=list)
    results: List[ToolExecutionResult] = field(default_factory=list)
    is_executed: bool = False
    
    def add(self, call: ToolCall) -> None:
        """Добавить вызов"""
        self.calls.append(call)
    
    def add_result(self, result: ToolExecutionResult) -> None:
        """Добавить результат"""
        self.results.append(result)
        if len(self.results) == len(self.calls):
            self.is_executed = True
    
    def get_result_for_call(self, call_id: str) -> Optional[ToolExecutionResult]:
        """Получить результат по ID вызова"""
        for result in self.results:
            if result.tool_call_id == call_id:
                return result
        return None
    
    def to_assistant_message(self) -> Dict[str, Any]:
        """
        Создать assistant message с tool_calls для LLM
        """
        return {
            "role": "assistant",
            "content": None,  # При tool_calls content обычно None
            "tool_calls": [call.to_openai_format() for call in self.calls]
        }
    
    def to_tool_messages(self) -> List[Dict[str, Any]]:
        """
        Создать tool messages с результатами для отправки в LLM
        """
        return [result.to_message() for result in self.results]
    
    @property
    def all_successful(self) -> bool:
        """Все ли вызовы успешны"""
        return all(r.success for r in self.results)
    
    @property
    def has_errors(self) -> bool:
        """Есть ли ошибки"""
        return any(not r.success for r in self.results)
    
    def __len__(self) -> int:
        return len(self.calls)
    
    def __bool__(self) -> bool:
        return len(self.calls) > 0
    
    def __repr__(self) -> str:
        status = "executed" if self.is_executed else "pending"
        return f"<ToolCallBatch {len(self.calls)} calls, {status}>"
