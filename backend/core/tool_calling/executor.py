"""
Tool Executor

Универсальный исполнитель инструментов.
Объединяет native tool calling и text fallback в единый интерфейс.
"""

import time
import logging
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import ToolCall, ToolCallBatch, ToolExecutionResult, ToolCallSource
from .text_extractor import ToolCallExtractor

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Универсальный исполнитель инструментов
    
    Отвечает за:
    1. Выполнение ToolCall с помощью зарегистрированных инструментов
    2. Параллельное выполнение (если разрешено)
    3. Обработку ошибок и таймаутов
    4. Логирование результатов
    
    Пример использования:
        executor = ToolExecutor(session_path="/path/to/session")
        
        # Выполнить один вызов
        result = executor.execute(tool_call)
        
        # Выполнить batch
        batch = executor.execute_batch(tool_calls)
    """
    
    def __init__(
        self,
        session_path: Optional[str] = None,
        parallel: bool = False,
        max_workers: int = 4,
        timeout: float = 60.0
    ):
        """
        Args:
            session_path: Путь к директории сессии (для file tools)
            parallel: Разрешить параллельное выполнение
            max_workers: Максимум параллельных воркеров
            timeout: Таймаут на один инструмент (секунды)
        """
        self.session_path = session_path
        self.parallel = parallel
        self.max_workers = max_workers
        self.timeout = timeout
        
        # Кэш экземпляров инструментов
        self._tool_instances: Dict[str, Any] = {}
        
        # Text extractor для fallback
        self._extractor = ToolCallExtractor()
    
    def execute(self, call: ToolCall) -> ToolExecutionResult:
        """
        Выполнить один tool call
        
        Args:
            call: ToolCall для выполнения
            
        Returns:
            ToolExecutionResult с результатом
        """
        start_time = time.time()
        
        try:
            # Получить экземпляр инструмента
            tool = self._get_tool_instance(call.name)
            
            if tool is None:
                return ToolExecutionResult(
                    tool_call_id=call.id,
                    tool_name=call.name,
                    success=False,
                    error=f"Tool not found: {call.name}"
                )
            
            # Выполнить
            result = tool.execute(**call.arguments)
            execution_time = (time.time() - start_time) * 1000
            
            # Конвертировать в ToolExecutionResult
            return ToolExecutionResult.from_tool_result(
                tool_call=call,
                result=result,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.exception(f"Tool execution failed: {call.name}")
            
            return ToolExecutionResult(
                tool_call_id=call.id,
                tool_name=call.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def execute_batch(self, calls: List[ToolCall]) -> ToolCallBatch:
        """
        Выполнить группу tool calls
        
        Args:
            calls: Список ToolCall для выполнения
            
        Returns:
            ToolCallBatch с результатами
        """
        batch = ToolCallBatch(calls=calls)
        
        if not calls:
            batch.is_executed = True
            return batch
        
        if self.parallel and len(calls) > 1:
            # Параллельное выполнение
            results = self._execute_parallel(calls)
        else:
            # Последовательное выполнение
            results = [self.execute(call) for call in calls]
        
        for result in results:
            batch.add_result(result)
        
        return batch
    
    def execute_from_text(self, text: str) -> ToolCallBatch:
        """
        Извлечь tool calls из текста и выполнить
        
        Используется как fallback когда модель не поддерживает
        native tool calling.
        
        Args:
            text: Текст ответа LLM
            
        Returns:
            ToolCallBatch с результатами
        """
        calls = self._extractor.extract(text)
        
        if not calls:
            logger.debug("No tool calls extracted from text")
            return ToolCallBatch()
        
        logger.info(f"Extracted {len(calls)} tool calls from text")
        return self.execute_batch(calls)
    
    def execute_with_fallback(
        self,
        native_calls: List[ToolCall],
        text_response: str
    ) -> ToolCallBatch:
        """
        Выполнить с fallback на текстовый парсинг
        
        Если есть native tool calls - использует их.
        Иначе пытается извлечь из текста.
        
        Args:
            native_calls: Tool calls из native API (может быть пустым)
            text_response: Текстовый ответ LLM
            
        Returns:
            ToolCallBatch с результатами
        """
        if native_calls:
            logger.debug(f"Using {len(native_calls)} native tool calls")
            return self.execute_batch(native_calls)
        
        # Fallback на текстовый парсинг
        logger.debug("No native calls, trying text extraction")
        return self.execute_from_text(text_response)
    
    def _get_tool_instance(self, name: str) -> Optional[Any]:
        """Получить экземпляр инструмента (с кэшированием)"""
        
        if name in self._tool_instances:
            return self._tool_instances[name]
        
        # Импортируем registry
        from backend.tools import tool_registry
        
        # Создаём экземпляр
        instance = tool_registry.get_instance(
            name=name,
            session_path=self.session_path
        )
        
        if instance:
            self._tool_instances[name] = instance
        
        return instance
    
    def _execute_parallel(self, calls: List[ToolCall]) -> List[ToolExecutionResult]:
        """Параллельное выполнение вызовов"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Отправляем все задачи
            future_to_call = {
                executor.submit(self.execute, call): call
                for call in calls
            }
            
            # Собираем результаты
            for future in as_completed(future_to_call):
                call = future_to_call[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                except Exception as e:
                    results.append(ToolExecutionResult(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        success=False,
                        error=f"Execution error: {str(e)}"
                    ))
        
        # Сортируем по порядку исходных вызовов
        call_order = {call.id: i for i, call in enumerate(calls)}
        results.sort(key=lambda r: call_order.get(r.tool_call_id, 999))
        
        return results
    
    def get_available_tools(self) -> List[str]:
        """Получить список доступных инструментов"""
        from backend.tools import tool_registry
        return tool_registry.list_all()
    
    def register_custom_tool(self, name: str, executor_func: Callable) -> None:
        """
        Зарегистрировать пользовательский инструмент
        
        Args:
            name: Имя инструмента
            executor_func: Функция-исполнитель (принимает **kwargs)
        """
        # Создаём wrapper
        class CustomTool:
            def execute(self, **kwargs):
                return executor_func(**kwargs)
        
        self._tool_instances[name] = CustomTool()


class ToolCallManager:
    """
    Высокоуровневый менеджер для управления tool calling
    
    Объединяет:
    - NativeToolHandler для подготовки запросов
    - ToolExecutor для выполнения
    - Multi-turn conversation management
    
    Пример использования:
        manager = ToolCallManager(session_path="/path/to/session")
        
        # Подготовить запрос с tools
        request_params = manager.prepare_request(messages)
        
        # После получения ответа
        batch, should_continue = manager.process_response(response)
        
        if should_continue:
            # Добавить результаты в историю и продолжить
            messages.extend(manager.get_followup_messages(batch))
    """
    
    def __init__(
        self,
        session_path: Optional[str] = None,
        agent_type: str = "coder",
        enable_parallel: bool = False
    ):
        self.session_path = session_path
        self.agent_type = agent_type
        
        # Инициализация компонентов
        from .native_handler import NativeToolHandler, get_coder_tools
        
        self.handler = NativeToolHandler()
        self.executor = ToolExecutor(
            session_path=session_path,
            parallel=enable_parallel
        )
        self.extractor = ToolCallExtractor()
        
        # Добавляем инструменты для агента
        if agent_type == "coder":
            for tool in get_coder_tools():
                self.handler.add_tool(tool)
        else:
            self.handler.add_tools_from_registry(agent_type)
    
    def prepare_request(self, format: str = "openai") -> Dict[str, Any]:
        """
        Подготовить параметры для API запроса
        
        Returns:
            Dict с tools и tool_choice для добавления в запрос
        """
        return self.handler.prepare_request_params(format)
    
    def process_response(
        self,
        response: Dict[str, Any],
        text_content: str = None
    ) -> tuple[ToolCallBatch, bool]:
        """
        Обработать ответ API
        
        Args:
            response: Ответ от API (dict)
            text_content: Текстовое содержимое ответа (для fallback)
            
        Returns:
            (ToolCallBatch, should_continue) - batch и флаг продолжения
        """
        # Парсим native tool calls
        batch = self.handler.parse_response(response)
        
        # Если нет native calls, пробуем text extraction
        if not batch and text_content:
            calls = self.extractor.extract(text_content)
            batch = ToolCallBatch(calls=calls)
        
        if not batch:
            return ToolCallBatch(), False
        
        # Выполняем
        executed_batch = self.executor.execute_batch(batch.calls)
        
        # Проверяем finish_reason
        finish_reason = response.get("choices", [{}])[0].get("finish_reason", "")
        should_continue = finish_reason == "tool_calls" or len(executed_batch.calls) > 0
        
        return executed_batch, should_continue
    
    def get_followup_messages(self, batch: ToolCallBatch) -> List[Dict[str, Any]]:
        """
        Получить messages для продолжения conversation
        
        Args:
            batch: Выполненный ToolCallBatch
            
        Returns:
            Список messages (assistant + tool results)
        """
        return self.handler.format_results_for_llm(batch)
    
    def format_results_summary(self, batch: ToolCallBatch) -> str:
        """
        Форматировать результаты для вывода пользователю
        
        Args:
            batch: Выполненный ToolCallBatch
            
        Returns:
            Человекочитаемое резюме
        """
        if not batch or not batch.results:
            return ""
        
        lines = ["## Результаты выполнения инструментов:\n"]
        
        for result in batch.results:
            status = "✅" if result.success else "❌"
            lines.append(f"### {status} {result.tool_name}")
            
            if result.success:
                if result.data:
                    data_str = str(result.data)
                    if len(data_str) > 500:
                        data_str = data_str[:500] + "..."
                    lines.append(f"```\n{data_str}\n```")
            else:
                lines.append(f"Ошибка: {result.error}")
            
            if result.execution_time_ms:
                lines.append(f"*Время: {result.execution_time_ms:.1f}мс*")
            
            lines.append("")
        
        return "\n".join(lines)
