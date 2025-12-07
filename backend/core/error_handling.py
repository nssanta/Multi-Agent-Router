"""
Error handling и logging middleware для AI Agent.
Обеспечивает централизованную обработку ошибок и логирование.
"""
import logging
import traceback
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from functools import wraps

# Настройка логгера
logger = logging.getLogger("ai_agent")
logger.setLevel(logging.DEBUG)

# Файловый handler для логов
log_dir = Path("workspace/logs")
log_dir.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(
    log_dir / f"agent_{datetime.now().strftime('%Y%m%d')}.log",
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(levelname)s: %(message)s'
))
logger.addHandler(console_handler)


class AgentError(Exception):
    """Базовый класс для ошибок агента."""
    
    def __init__(self, message: str, error_code: str = "AGENT_ERROR", 
                 user_message: str = None, recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or self._default_user_message()
        self.recoverable = recoverable
        self.timestamp = datetime.now().isoformat()
    
    def _default_user_message(self) -> str:
        return "Произошла ошибка. Попробуйте повторить запрос."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp
        }


class ToolExecutionError(AgentError):
    """Ошибка выполнения инструмента."""
    
    def __init__(self, tool_name: str, message: str):
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            error_code="TOOL_ERROR",
            user_message=f"Инструмент '{tool_name}' не смог выполнить операцию. Попробуйте повторить.",
            recoverable=True
        )
        self.tool_name = tool_name


class LLMError(AgentError):
    """Ошибка взаимодействия с LLM."""
    
    def __init__(self, message: str, provider: str = None, status_code: int = None):
        if status_code == 429:
            user_msg = "Превышен лимит запросов. Подождите немного или смените модель."
            recoverable = True
        elif status_code == 400:
            user_msg = "Некорректный запрос к модели. Попробуйте другой запрос."
            recoverable = True
        elif status_code in [500, 502, 503]:
            user_msg = "Сервис временно недоступен. Попробуйте позже."
            recoverable = True
        else:
            user_msg = "Ошибка при обращении к AI модели. Попробуйте повторить."
            recoverable = True
        
        super().__init__(
            message=message,
            error_code=f"LLM_ERROR_{status_code or 'UNKNOWN'}",
            user_message=user_msg,
            recoverable=recoverable
        )
        self.provider = provider
        self.status_code = status_code


class SessionError(AgentError):
    """Ошибка сессии."""
    
    def __init__(self, message: str, session_id: str = None):
        super().__init__(
            message=message,
            error_code="SESSION_ERROR",
            user_message="Ошибка сессии. Попробуйте создать новый чат.",
            recoverable=False
        )
        self.session_id = session_id


class FileOperationError(AgentError):
    """Ошибка файловой операции."""
    
    def __init__(self, message: str, filepath: str = None):
        super().__init__(
            message=message,
            error_code="FILE_ERROR",
            user_message="Ошибка при работе с файлом. Проверьте путь и права доступа.",
            recoverable=True
        )
        self.filepath = filepath


def error_handler(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок.
    :param func: декорируемая функция
    :return: обернутая функция
    """
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AgentError as e:
            logger.error(f"{e.error_code}: {e.message}", exc_info=True)
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return {
                "success": False,
                "error": {
                    "error_code": "UNEXPECTED_ERROR",
                    "message": str(e),
                    "user_message": "Произошла непредвиденная ошибка. Попробуйте повторить или начать новый чат.",
                    "recoverable": True,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    return wrapper


async def async_error_handler(func: Callable) -> Callable:
    """
    Асинхронный декоратор для обработки ошибок.
    :param func: декорируемая асинхронная функция
    :return: обернутая асинхронная функция
    """
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AgentError as e:
            logger.error(f"{e.error_code}: {e.message}", exc_info=True)
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return {
                "success": False,
                "error": {
                    "error_code": "UNEXPECTED_ERROR",
                    "message": str(e),
                    "user_message": "Произошла непредвиденная ошибка. Попробуйте повторить или начать новый чат.",
                    "recoverable": True,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    return wrapper


def log_agent_action(session_id: str, action: str, details: Dict[str, Any] = None):
    """
    Логируем действия агента.
    :param session_id: ID сессии
    :param action: название действия
    :param details: дополнительные детали (словарь)
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "action": action,
        "details": details or {}
    }
    logger.info(f"Agent action: {json.dumps(log_entry, ensure_ascii=False)}")


def format_error_for_user(error: AgentError) -> str:
    """
    Форматируем ошибку для отображения пользователю.
    :param error: объект ошибки AgentError
    :return: отформатированное сообщение об ошибке
    """
    if error.recoverable:
        return f"⚠️ {error.user_message}\n\n💡 Попробуйте повторить запрос или нажмите кнопку Retry."
    else:
        return f"❌ {error.user_message}\n\n🔄 Рекомендуем начать новый чат."


# Экспорт
__all__ = [
    'AgentError',
    'ToolExecutionError', 
    'LLMError',
    'SessionError',
    'FileOperationError',
    'error_handler',
    'async_error_handler',
    'log_agent_action',
    'format_error_for_user',
    'logger'
]
