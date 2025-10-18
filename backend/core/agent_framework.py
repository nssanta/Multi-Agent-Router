"""
Собственный Agent Framework - замена google.adk.agents

Реализует основные классы:
- Agent: базовый агент с LLM
- SequentialAgent: последовательное выполнение
- ParallelAgent: параллельное выполнение
- LoopAgent: циклическое выполнение
- AgentState: состояние агента (замена CallbackContext)
"""

from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import logging
import re

from .llm_provider import BaseLLMProvider
from .code_executor import LocalCodeExecutor

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """
    Состояние агента (замена CallbackContext из ADK)
    
    Хранит данные между вызовами агентов и callbacks
    """
    data: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default=None):
        """Получить значение из state"""
        return self.data.get(key, default)
    
    def set(self, key: str, value):
        """Установить значение в state"""
        self.data[key] = value
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def __contains__(self, key):
        return key in self.data
    
    def to_dict(self) -> Dict:
        """Экспортировать в dict для сохранения"""
        return self.data.copy()


class Agent:
    """
    Базовый класс агента (замена google.adk.agents.Agent)
    
    Поддерживает:
    - Промты (instruction)
    - Callbacks (before/after)
    - Tools (пока не реализовано)
    - Code executor (для аналитических агентов)
    """
    
    def __init__(
        self,
        name: str,
        llm_provider: BaseLLMProvider,
        instruction: str | Callable[[AgentState], str],
        global_instruction: str = "",
        tools: Optional[List[Callable]] = None,
        code_executor: Optional[LocalCodeExecutor] = None,
        before_callback: Optional[Callable[[AgentState], None]] = None,
        after_callback: Optional[Callable[[AgentState, str], None]] = None,
        include_contents: str = "all",  # "all", "last", "none"
        temperature: float = 0.7
    ):
        self.name = name
        self.llm_provider = llm_provider
        self.instruction = instruction
        self.global_instruction = global_instruction
        self.tools = tools or []
        self.code_executor = code_executor
        self.before_callback = before_callback
        self.after_callback = after_callback
        self.include_contents = include_contents
        self.temperature = temperature
        self.state = AgentState()
    
    def _get_instruction(self) -> str:
        """Получить instruction (может быть строкой или функцией)"""
        if callable(self.instruction):
            return self.instruction(self.state)
        return self.instruction
    
    def run(self, user_input: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Запустить агента
        
        Args:
            user_input: Текущее сообщение пользователя
            history: История предыдущих сообщений [{"role": "user", "content": "..."}, ...]
        
        Returns:
            Ответ агента
        """
        from datetime import datetime
        import json
        
        logger.info(f"[{self.name}] Starting")
        
        # Сохранить user_input в state для доступа в callbacks
        self.state.set("current_user_input", user_input)
        
        # Before callback
        if self.before_callback:
            self.before_callback(self.state)
        
        # Построить промт с историей
        instruction = self._get_instruction()
        
        # Базовый промпт
        full_prompt = f"{self.global_instruction}\n\n{instruction}\n\n"
        
        # Добавить историю сообщений (если есть)
        if history:
            full_prompt += "**Conversation History:**\n"
            for msg in history[-10:]:  # Последние 10 сообщений для контекста
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    full_prompt += f"User: {content}\n"
                elif role == "assistant":
                    full_prompt += f"Assistant: {content}\n"
            full_prompt += "\n"
        
        # Текущее сообщение
        full_prompt += f"User: {user_input}"
        
        # Логировать запрос (если есть code_executor с logs_path)
        if self.code_executor and hasattr(self.code_executor, 'logs_path'):
            self._log_llm_request(user_input, full_prompt)
        
        # Вызвать LLM
        try:
            response = self.llm_provider.generate(full_prompt, temperature=self.temperature)
            # Логировать ответ
            if self.code_executor and hasattr(self.code_executor, 'logs_path'):
                self._log_llm_response(response, success=True)
        except Exception as e:
            logger.error(f"LLM generation error in agent '{self.name}': {e}")
            error_msg = f"Sorry, I encountered an error while processing your request: {e}"
            # Логировать ошибку
            if self.code_executor and hasattr(self.code_executor, 'logs_path'):
                self._log_llm_response(error_msg, success=False, error=str(e))
            return error_msg
        
        # Если есть code executor - выполнить код
        if self.code_executor:
            # Извлечь код из ответа (если есть ```python блоки)
            code = self._extract_code(response)
            if code:
                result = self.code_executor.execute_code(code)
                # Добавить результат в response
                response += f"\n\nCode execution result:\n{result['stdout']}"
                # Сохранить в state
                self.state.set(f"{self.name}_exec_result", result)
        
        # After callback - может вернуть модифицированный response
        if self.after_callback:
            modified_response = self.after_callback(self.state, response)
            # Если callback вернул новое значение - использовать его
            if modified_response is not None:
                response = modified_response
        
        logger.info(f"[{self.name}] Complete")
        return response
    
    def _log_llm_request(self, user_input: str, full_prompt: str):
        """Логировать LLM запрос"""
        if not self.code_executor:
            return
        
        from datetime import datetime
        import json
        
        log_file = self.code_executor.logs_path / f"agent_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_request.log"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "user_input": user_input,
            "full_prompt": full_prompt,
            "temperature": self.temperature
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    def _log_llm_response(self, response: str, success: bool = True, error: str = None):
        """Логировать LLM ответ"""
        if not self.code_executor:
            return
        
        from datetime import datetime
        import json
        
        log_file = self.code_executor.logs_path / f"agent_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_response.log"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "response": response,
            "success": success
        }
        
        if error:
            log_data["error"] = error
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    def stream(self, user_input: str):
        """Стриминг ответа"""
        if self.before_callback:
            self.before_callback(self.state)
        
        instruction = self._get_instruction()
        full_prompt = f"{self.global_instruction}\n\n{instruction}\n\nUser: {user_input}"
        
        for chunk in self.llm_provider.stream(full_prompt, temperature=self.temperature):
            yield chunk
    
    def _extract_code(self, text: str) -> Optional[str]:
        """Извлечь Python код из markdown блоков"""
        pattern = r"```python\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return matches[0] if matches else None


class SequentialAgent:
    """
    Последовательное выполнение субагентов
    
    Каждый агент получает результат предыдущего как input
    """
    
    def __init__(
        self,
        name: str,
        sub_agents: List[Agent],
        description: str = "",
        before_callback: Optional[Callable[[AgentState], None]] = None,
        after_callback: Optional[Callable[[AgentState], None]] = None,
    ):
        self.name = name
        self.sub_agents = sub_agents
        self.description = description
        self.before_callback = before_callback
        self.after_callback = after_callback
        self.state = AgentState()
    
    def run(self, user_input: str) -> str:
        """Запустить последовательно всех субагентов"""
        logger.info(f"[{self.name}] Sequential start")
        
        if self.before_callback:
            self.before_callback(self.state)
        
        result = user_input
        for agent in self.sub_agents:
            # Поделиться state между агентами
            agent.state = self.state
            result = agent.run(result)
        
        if self.after_callback:
            self.after_callback(self.state)
        
        logger.info(f"[{self.name}] Sequential complete")
        return result


class ParallelAgent:
    """
    Параллельное выполнение субагентов
    
    Все агенты запускаются одновременно
    """
    
    def __init__(
        self,
        name: str,
        sub_agents: List[Agent],
        description: str = "",
        max_workers: int = None
    ):
        self.name = name
        self.sub_agents = sub_agents
        self.description = description
        self.max_workers = max_workers or len(sub_agents)
        self.state = AgentState()
    
    def run(self, user_input: str) -> str:
        """Запустить параллельно всех субагентов"""
        logger.info(f"[{self.name}] Parallel start ({len(self.sub_agents)} agents)")
        
        def run_agent(agent):
            agent.state = self.state
            return agent.run(user_input)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(run_agent, self.sub_agents))
        
        logger.info(f"[{self.name}] Parallel complete")
        return "\n\n".join(results)


class LoopAgent:
    """
    Циклическое выполнение агента
    
    Повторяет агента N раз или пока не выполнится условие
    """
    
    def __init__(
        self,
        name: str,
        sub_agents: List[Agent],
        max_iterations: int,
        description: str = "",
        before_callback: Optional[Callable[[AgentState], None]] = None,
    ):
        self.name = name
        self.sub_agents = sub_agents
        self.max_iterations = max_iterations
        self.description = description
        self.before_callback = before_callback
        self.state = AgentState()
    
    def run(self, user_input: str) -> str:
        """Запустить агента в цикле"""
        logger.info(f"[{self.name}] Loop start (max {self.max_iterations} iterations)")
        
        if self.before_callback:
            self.before_callback(self.state)
        
        result = user_input
        for i in range(self.max_iterations):
            logger.info(f"[{self.name}] Iteration {i+1}/{self.max_iterations}")
            
            # Выполнить всех субагентов
            for agent in self.sub_agents:
                agent.state = self.state
                result = agent.run(result)
            
            # TODO: добавить условие выхода из цикла
        
        logger.info(f"[{self.name}] Loop complete")
        return result