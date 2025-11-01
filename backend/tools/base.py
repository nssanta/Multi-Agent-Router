"""
Базовые классы для модульной системы инструментов

Классы:
- ToolResult: результат выполнения инструмента
- BaseTool: абстрактный базовый класс для всех инструментов
- ToolRegistry: реестр всех доступных инструментов
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    """Статус выполнения инструмента"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # Частичный успех


@dataclass
class ToolResult:
    """Результат выполнения инструмента"""
    
    status: ToolStatus
    data: Any = None  # Основные данные результата
    message: str = ""  # Человекочитаемое сообщение
    error: Optional[str] = None  # Описание ошибки, если есть
    metadata: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные
    
    @classmethod
    def success(cls, data: Any = None, message: str = "") -> "ToolResult":
        """Создать успешный результат"""
        return cls(status=ToolStatus.SUCCESS, data=data, message=message)
    
    @classmethod
    def error(cls, error: str, data: Any = None) -> "ToolResult":
        """Создать результат с ошибкой"""
        return cls(status=ToolStatus.ERROR, error=error, data=data)
    
    @classmethod
    def partial(cls, data: Any, message: str = "", error: str = None) -> "ToolResult":
        """Создать частично успешный результат"""
        return cls(status=ToolStatus.PARTIAL, data=data, message=message, error=error)
    
    def is_success(self) -> bool:
        """Проверить успешность"""
        return self.status == ToolStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализовать в словарь"""
        return {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """
    Абстрактный базовый класс для всех инструментов
    
    Каждый инструмент должен:
    - Иметь уникальное имя (name)
    - Иметь описание для LLM (description)
    - Определять параметры (parameters)
    - Реализовать execute()
    
    Пример использования:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Делает что-то полезное"
            parameters = {
                "input": {"type": "string", "description": "Входные данные"}
            }
            
            def execute(self, input: str) -> ToolResult:
                return ToolResult.success(data=input.upper())
    """
    
    # Обязательные атрибуты (должны быть переопределены)
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    
    # Опциональные атрибуты
    required_params: List[str] = []  # Обязательные параметры
    agent_types: List[str] = ["all"]  # Для каких агентов доступен ("all" = для всех)
    
    def __init__(self, session_path: Optional[str] = None, **config):
        """
        Инициализация инструмента
        
        Args:
            session_path: Путь к директории сессии (для file tools)
            **config: Дополнительная конфигурация
        """
        self.session_path = session_path
        self.config = config
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Выполнить инструмент
        
        Args:
            **kwargs: Параметры инструмента
            
        Returns:
            ToolResult с результатом выполнения
        """
        pass
    
    def validate_params(self, **kwargs) -> Optional[str]:
        """
        Валидация входных параметров
        
        Returns:
            None если всё ок, иначе сообщение об ошибке
        """
        for param in self.required_params:
            if param not in kwargs or kwargs[param] is None:
                return f"Missing required parameter: {param}"
        return None
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Получить JSON Schema для LLM (OpenAI function calling format)
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required_params
            }
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}'>"


class ToolRegistry:
    """
    Реестр всех доступных инструментов
    
    Позволяет:
    - Регистрировать инструменты
    - Получать инструменты по имени
    - Фильтровать по типу агента
    
    Пример:
        registry = ToolRegistry()
        registry.register(ReadFileTool)
        registry.register(WriteFileTool)
        
        coder_tools = registry.get_tools_for_agent("coder")
    """
    
    _instance: Optional["ToolRegistry"] = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, Type[BaseTool]] = {}
        return cls._instance
    
    def register(self, tool_class: Type[BaseTool]) -> None:
        """
        Зарегистрировать класс инструмента
        
        Args:
            tool_class: Класс, наследующий BaseTool
        """
        if not issubclass(tool_class, BaseTool):
            raise TypeError(f"{tool_class} must inherit from BaseTool")
        
        if not tool_class.name:
            raise ValueError(f"{tool_class.__name__} must have a non-empty 'name' attribute")
        
        if tool_class.name in self._tools:
            logger.warning(f"Tool '{tool_class.name}' already registered, replacing")
        
        self._tools[tool_class.name] = tool_class
        logger.debug(f"Registered tool: {tool_class.name}")
    
    def get(self, name: str) -> Optional[Type[BaseTool]]:
        """Получить класс инструмента по имени"""
        return self._tools.get(name)
    
    def get_instance(self, name: str, session_path: str = None, **config) -> Optional[BaseTool]:
        """
        Получить экземпляр инструмента
        
        Args:
            name: Имя инструмента
            session_path: Путь к сессии
            **config: Конфигурация
            
        Returns:
            Экземпляр или None
        """
        tool_class = self.get(name)
        if tool_class:
            return tool_class(session_path=session_path, **config)
        return None
    
    def get_tools_for_agent(
        self, 
        agent_type: str, 
        session_path: str = None,
        **config
    ) -> List[BaseTool]:
        """
        Получить все инструменты, доступные для агента
        
        Args:
            agent_type: Тип агента ("dialog", "coder", "mle", и т.д.)
            session_path: Путь к сессии
            **config: Дополнительная конфигурация
            
        Returns:
            Список экземпляров инструментов
        """
        tools = []
        for tool_class in self._tools.values():
            if "all" in tool_class.agent_types or agent_type in tool_class.agent_types:
                tools.append(tool_class(session_path=session_path, **config))
        return tools
    
    def list_all(self) -> List[str]:
        """Список имён всех зарегистрированных инструментов"""
        return list(self._tools.keys())
    
    def get_schemas_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """Получить JSON схемы всех инструментов для агента"""
        schemas = []
        for tool_class in self._tools.values():
            if "all" in tool_class.agent_types or agent_type in tool_class.agent_types:
                # Создаём временный экземпляр для получения схемы
                tool = tool_class()
                schemas.append(tool.get_schema())
        return schemas


# Глобальный реестр инструментов
tool_registry = ToolRegistry()


def register_tool(tool_class: Type[BaseTool]) -> Type[BaseTool]:
    """
    Декоратор для регистрации инструмента
    
    Пример:
        @register_tool
        class MyTool(BaseTool):
            name = "my_tool"
            ...
    """
    tool_registry.register(tool_class)
    return tool_class
