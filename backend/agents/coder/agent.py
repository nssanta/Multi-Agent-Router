"""
Coder Agent - AI ассистент для программирования.

Использует:
- Tree of Thoughts для анализа сложных задач
- Verifier для проверки кода
- File Tools для работы с файлами
"""

from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
import re
import logging
import json
from datetime import datetime

from backend.core.agent_framework import Agent, AgentState
from backend.core.llm_provider import BaseLLMProvider
from backend.tools import tool_registry, ToolResult
from .prompts import get_coder_instruction
from .tree_of_thoughts import TreeOfThoughts, run_tree_of_thoughts
from .verifier import CodeVerifier, verify_code, VerificationStatus

logger = logging.getLogger(__name__)


def create_coder_agent(
    llm_provider: BaseLLMProvider,
    session_path: Path,
    use_tree_of_thoughts: bool = True,
    num_branches: int = 2,
    use_verifier: bool = True,
    verifier_model_id: Optional[str] = None
) -> Agent:
    """
    Создает Coder Agent с полным функционалом.
    
    :param llm_provider: LLM провайдер
    :param session_path: Путь к директории сессии
    :param use_tree_of_thoughts: Включить ToT для сложных задач
    :param num_branches: Количество веток мышления (по умолчанию 2)
    :param use_verifier: Включить верификацию кода
    :param verifier_model_id: ID модели для верификатора (None = та же модель)
    :return: Сконфигурированный Agent
    """
    
    # Инициализация компонентов
    tot = TreeOfThoughts(llm_provider, num_branches=num_branches) if use_tree_of_thoughts else None
    verifier = CodeVerifier(llm_provider, verifier_model_id) if use_verifier else None
    
    # Получаем tools для coder
    tools = tool_registry.get_tools_for_agent("coder", session_path=str(session_path))
    
    def get_instruction_with_context(state: AgentState) -> str:
        """
        Динамически добавляет контекст в промпт.
        :param state: состояние агента
        :return: инструкция с контекстом
        """
        
        base_instruction = get_coder_instruction()
        
        # Добавляем информацию о файлах в сессии
        workspace = session_path / "workspace"
        input_dir = session_path / "input"
        
        files_info = []
        
        # Файлы в workspace
        if workspace.exists():
            for f in workspace.rglob("*"):
                if f.is_file():
                    rel_path = f.relative_to(workspace)
                    files_info.append(f"  - workspace/{rel_path}")
        
        # Файлы в input
        if input_dir.exists():
            for f in input_dir.iterdir():
                if f.is_file():
                    files_info.append(f"  - input/{f.name}")
        
        files_section = "\n".join(files_info) if files_info else "  Нет файлов"
        
        # ToT и Verifier статус
        features = []
        if use_tree_of_thoughts:
            features.append(f"- Tree of Thoughts: {num_branches} ветки")
        if use_verifier:
            features.append("- Верификация кода: включена")
        
        features_section = "\n".join(features) if features else "Стандартный режим"
        
        context = f"""

## Текущий контекст сессии:

### Файлы в сессии:
{files_section}

### Активные функции:
{features_section}

### Параметры:
- session_path: {session_path}
- Дата: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""
        
        return base_instruction + context
    
    def before_run(state: AgentState) -> None:
        """
        Выполняет подготовку перед запуском.
        :param state: состояние агента
        """
        
        # Сохраняем компоненты в state для использования в after_run
        state.set("tot", tot)
        state.set("verifier", verifier)
        state.set("session_path", str(session_path))
        state.set("tools", tools)
        
        # Инициализируем список выполненных действий
        if "actions" not in state.data:
            state.set("actions", [])
        
        logger.debug(f"Coder Agent: before_run, session={session_path}")
    
    def after_run(state: AgentState, response: str) -> str:
        """
        Выполняет пост-обработку ответа агента:
        1. Ищем команды инструментов в ответе
        2. Выполняем инструменты
        3. Если есть код - верифицируем
        4. Если сложная задача - запускаем ToT
        
        :param state: состояние агента
        :param response: ответ LLM
        :return: обновленный ответ
        """
        
        original_response = response
        actions = state.get("actions", [])
        
        # Шаг 1: Ищем и выполняем tool commands
        tool_commands = _extract_tool_commands(response)
        
        if tool_commands:
            tool_results = []
            for cmd in tool_commands:
                result = _execute_tool(cmd, tools)
                tool_results.append(result)
                actions.append({
                    "type": "tool",
                    "tool": cmd.get("tool"),
                    "result": result.to_dict() if isinstance(result, ToolResult) else str(result)
                })
            
            # Добавляем результаты к ответу
            results_text = _format_tool_results(tool_commands, tool_results)
            response = response + "\n\n## Результаты выполнения:\n" + results_text
        
        # Шаг 2: Проверяем, нужен ли Tree of Thoughts
        tot_instance = state.get("tot")
        user_message = state.get("last_user_message", "")
        
        # ToT для сложных задач (эвристика: длинное сообщение или ключевые слова)
        if tot_instance and _should_use_tot(user_message, response):
            logger.info("Coder Agent: Activating Tree of Thoughts")
            
            try:
                tot_result = tot_instance.think(user_message, context=_get_context(state))
                
                # Добавляем ToT результат
                response = f"""## Tree of Thoughts Analysis

### Анализ задачи:
{tot_result.analysis}

### Выбранное решение (ветка {tot_result.best_branch.branch_id if tot_result.best_branch else '?'}):
{tot_result.final_solution}

### Оценка:
{tot_result.evaluation[:500]}...\n"""
                actions.append({
                    "type": "tree_of_thoughts",
                    "branches": len(tot_result.branches),
                    "best_branch": tot_result.best_branch.branch_id if tot_result.best_branch else None
                })
            except Exception as e:
                logger.error(f"ToT failed: {e}")
                response = original_response + f"\n\n⚠️ Tree of Thoughts анализ не удался: {str(e)}"
        
        # Шаг 3: Верификация кода
        verifier_instance = state.get("verifier")
        
        # Извлекаем код из ОРИГИНАЛЬНОГО ответа (до добавления результатов tools)
        # чтобы верифицировать только код от LLM, а не метаданные write_file
        code_blocks = _extract_code_blocks(original_response)
        
        if verifier_instance and code_blocks:
            verification_results = []
            
            for lang, code in code_blocks:
                if lang in ["python", "py", ""]:
                    try:
                        result = verifier_instance.verify(code, "python", user_message)
                        verification_results.append((lang, result))
                        
                        actions.append({
                            "type": "verification",
                            "language": lang,
                            "status": result.status.value,
                            "issues_count": len(result.issues)
                        })
                    except Exception as e:
                        logger.error(f"Verification failed: {e}")
            
            # Добавляем результаты верификации
            if verification_results:
                response = response + "\n\n## Верификация кода:\n"
                for lang, result in verification_results:
                    response += f"\n### {lang or 'python'}: {result.summary}\n"
                    if result.issues:
                        response += "Найденные проблемы:\n"
                        for issue in result.issues[:5]:
                            line_info = f" (строка {issue.line})" if issue.line else ""
                            response += f"- [{issue.severity.value}]{line_info}: {issue.message}\n"
        
        # Сохраняем actions
        state.set("actions", actions)
        
        # Логируем
        _log_agent_run(session_path, user_message, response, actions)
        
        return response
    
    # Tool definitions для Native Tool Calling (Gemini)
    tool_definitions = [
        {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace (e.g., 'main.py', 'src/utils.py')"
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "read_file",
            "description": "Read the content of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_directory",
            "description": "List all files in the workspace directory",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "run_code",
            "description": "Execute Python code and return the output",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            }
        }
    ]
    
    # Создаём code_executor для выполнения инструментов
    from backend.core.code_executor import LocalCodeExecutor
    code_executor = LocalCodeExecutor(session_path=session_path)
    
    # Создаём агента
    agent = Agent(
        name="coder",
        llm_provider=llm_provider,
        instruction=get_instruction_with_context,
        tool_definitions=tool_definitions,  # Для native tool calling
        code_executor=code_executor,  # Для выполнения инструментов
        before_callback=before_run,
        after_callback=after_run,
        temperature=0.5  # Более детерминированный для кода
    )
    
    return agent


def _extract_tool_commands(text: str) -> List[Dict[str, Any]]:
    """
    Извлекает команды инструментов из текста.
    Использует новую универсальную систему ToolCallExtractor.
    :param text: текст ответа
    :return: список команд
    """
    from backend.core.tool_calling import ToolCallExtractor
    
    extractor = ToolCallExtractor()
    tool_calls = extractor.extract(text)
    
    # Конвертируем в старый формат для обратной совместимости
    commands = []
    for call in tool_calls:
        commands.append({
            "tool": call.name,
            "params": call.arguments
        })
    
    if commands:
        logger.info(f"Extracted {len(commands)} tool commands: {[c['tool'] for c in commands]}")
    
    return commands


def _execute_tool(
    command: Dict[str, Any], 
    tools: List[Any]
) -> ToolResult:
    """
    Выполняет инструмент.
    :param command: словарь с командой
    :param tools: список доступных инструментов
    :return: результат выполнения
    """
    
    tool_name = command.get("tool", "")
    params = command.get("params", {})
    
    # Находим инструмент
    tool = None
    for t in tools:
        if t.name == tool_name:
            tool = t
            break
    
    if not tool:
        return ToolResult.error(f"Tool not found: {tool_name}")
    
    try:
        return tool.execute(**params)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return ToolResult.error(str(e))


def _format_tool_results(
    commands: List[Dict], 
    results: List[ToolResult]
) -> str:
    """
    Форматирует результаты выполнения инструментов.
    :param commands: список команд
    :param results: список результатов
    :return: отформатированная строка
    """
    
    formatted = []
    
    for cmd, result in zip(commands, results):
        tool_name = cmd.get("tool", "unknown")
        status = "✅" if result.is_success() else "❌"
        
        formatted.append(f"### {status} {tool_name}")
        
        if result.message:
            formatted.append(f"{result.message}")
        
        if result.error:
            formatted.append(f"Ошибка: {result.error}")
        
        if result.data:
            # Ограничиваем вывод данных
            data_str = str(result.data)
            if len(data_str) > 500:
                data_str = data_str[:500] + "..."
            formatted.append(f"```\n{data_str}\n```")
        
        formatted.append("")
    
    return "\n".join(formatted)


def _should_use_tot(user_message: str, response: str) -> bool:
    """
    Определяет, нужен ли Tree of Thoughts.
    :param user_message: сообщение пользователя
    :param response: ответ агента
    :return: True если нужен ToT
    """
    
    # Эвристики:
    # 1. Длинное сообщение пользователя
    # 2. Ключевые слова для сложных задач
    # 3. Агент сам выражает неуверенность
    
    complex_keywords = [
        "сложн", "алгоритм", "оптимиз", "архитектур", "рефактор",
        "система", "паттерн", "дизайн", "implement", "design",
        "complex", "algorithm", "optimize", "refactor"
    ]
    
    # Проверяем длину
    if len(user_message) > 300:
        return True
    
    # Проверяем ключевые слова
    msg_lower = user_message.lower()
    for keyword in complex_keywords:
        if keyword in msg_lower:
            return True
    
    return False


def _extract_code_blocks(text: str) -> List[tuple]:
    """
    Извлекает блоки кода из markdown.
    :param text: текст markdown
    :return: список кортежей (язык, код)
    """
    
    pattern = r'```(\w*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    return [(lang, code.strip()) for lang, code in matches]


def _get_context(state: AgentState) -> str:
    """
    Получает контекст сессии для ToT.
    :param state: состояние агента
    :return: строка контекста
    """
    
    session_path = state.get("session_path", "")
    history = state.get("history", [])
    
    context_parts = []
    
    if history:
        # Последние несколько сообщений
        recent = history[-4:] if len(history) > 4 else history
        context_parts.append("Недавняя история:")
        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:200]
            context_parts.append(f"  {role}: {content}...")
    
    return "\n".join(context_parts)


def _log_agent_run(
    session_path: Path, 
    user_message: str, 
    response: str,
    actions: List[Dict]
) -> None:
    """
    Логирует запуск агента.
    :param session_path: путь к сессии
    :param user_message: сообщение пользователя
    :param response: ответ агента
    :param actions: список действий
    """
    
    logs_dir = session_path / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"coder_agent_{timestamp}.log"
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "agent": "coder",
        "user_message": user_message[:500],  # Ограничиваем
        "response_length": len(response),
        "actions": actions,
        "tot_used": any(a.get("type") == "tree_of_thoughts" for a in actions),
        "verification_used": any(a.get("type") == "verification" for a in actions)
    }
    
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write log: {e}")