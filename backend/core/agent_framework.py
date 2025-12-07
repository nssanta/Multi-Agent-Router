"""
Собственный Agent Framework - замена google.adk.agents

Реализует основные классы:
- Agent: базовый агент с LLM
- SequentialAgent: последовательное выполнение
- ParallelAgent: параллельное выполнение
- LoopAgent: циклическое выполнение
- AgentState: состояние агента (замена CallbackContext)
"""

from typing import Callable, Optional, Dict, List, Any, Iterator
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
        tool_definitions: Optional[List[Dict]] = None,  # For native tool calling
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
        self.tool_definitions = tool_definitions or []
        self.code_executor = code_executor
        self.before_callback = before_callback
        self.after_callback = after_callback
        self.include_contents = include_contents
        self.temperature = temperature
        self.state = AgentState()
    
    def _supports_native_tools(self) -> bool:
        """Проверить поддерживает ли провайдер native tool calling"""
        return (
            hasattr(self.llm_provider, 'supports_native_tools') and 
            self.llm_provider.supports_native_tools() and
            len(self.tool_definitions) > 0
        )
    
    def _get_instruction(self) -> str:
        """Получить instruction (может быть строкой или функцией)"""
        if callable(self.instruction):
            return self.instruction(self.state)
        return self.instruction
    
    def run(self, user_input: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Запустить агента (синхронная обертка над streaming)
        """
        response_content = ""
        for event in self.run_stream(user_input, history):
            if event["type"] == "token":
                response_content += event["content"]
        return response_content

    def run_stream(self, user_input: str, history: Optional[List[Dict[str, str]]] = None) -> Iterator[Dict[str, str]]:
        """
        Запустить агента в режиме стриминга с поддержкой multi-turn loops.
        
        Yields:
            Dict[str, str]: {
                "type": "token" | "status" | "error" | "log",
                "content": "..."
            }
        """
        from datetime import datetime
        import json
        
        logger.info(f"[{self.name}] Starting run_stream")
        
        # Init state
        self.state.set("current_user_input", user_input)
        if self.before_callback:
            self.before_callback(self.state)

        # Build initial history
        current_history = list(history) if history else []
        current_history.append({"role": "user", "content": user_input})
        
        max_turns = 15  # Limit autonomous turns
        last_tool_sig = None
        consecutive_malformed_count = 0
        
        for turn in range(max_turns):
            logger.info(f"[{self.name}] Turn {turn+1}/{max_turns}")
            
            # Prepare Prompt
            instruction = self._get_instruction()
            full_prompt = f"{self.global_instruction}\n\n{instruction}\n\n"
            
            # History
            if current_history:
                full_prompt += "**Conversation History:**\n"
                for msg in current_history[-20:]: # Last 20 messages
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        full_prompt += f"User: {content}\n"
                    elif role == "assistant":
                        full_prompt += f"Assistant: {content}\n"
                    elif role == "system": # Tool outputs
                        full_prompt += f"System: {content}\n"
                full_prompt += "\n"
            
            # Add "Response:" marker? Not strictly needed for chat models but helps
            # full_prompt += "Assistant: " 

            # Log request
            if self.code_executor and hasattr(self.code_executor, 'logs_path'):
                 self._log_llm_request(user_input, full_prompt)

            # --- GENERATION (Native Tools or Text-Based) ---
            full_response_text = ""
            tool_call = None
            yield {"type": "status", "content": "Thinking..."}
            
            try:
                # Check if we can use native tool calling
                use_native = self._supports_native_tools()
                
                if use_native:
                    # === NATIVE TOOL CALLING ===
                    logger.info(f"[{self.name}] Using native tool calling")
                    result = self.llm_provider.generate_with_tools(
                        full_prompt, 
                        self.tool_definitions,
                        temperature=self.temperature
                    )
                    
                    # Handle text response
                    if result.get("text"):
                        full_response_text = result["text"]
                        yield {"type": "token", "content": full_response_text}
                    
                    # Handle tool calls
                    if result.get("tool_calls"):
                        tc = result["tool_calls"][0]  # Take first tool call
                        tool_call = {
                            "tool": tc["name"],
                            "params": tc.get("args", {})
                        }
                        # Add visual indicator of tool call
                        tool_indicator = f"\n\n```json\n{{\"tool\": \"{tc['name']}\", \"params\": {json.dumps(tc.get('args', {}))}}}\n```"
                        full_response_text += tool_indicator
                        yield {"type": "token", "content": tool_indicator}
                else:
                    # === TEXT-BASED TOOL CALLING (fallback) ===
                    for chunk in self.llm_provider.stream(full_prompt, temperature=self.temperature):
                        full_response_text += chunk
                        yield {"type": "token", "content": chunk}
                    
                    # Extract tool call from text
                    tool_call = self._extract_json_tool_call(full_response_text)
                
                # Turn complete. Log it.
                if self.code_executor and hasattr(self.code_executor, 'logs_path'):
                    self._log_llm_response(full_response_text, success=True)
                    
                # Add assistant response to history
                current_history.append({"role": "assistant", "content": full_response_text})
                
                # --- TOOL EXECUTION ---
                
                if tool_call and self.code_executor:
                    consecutive_malformed_count = 0  # Reset counter on valid tool call
                    tool_name = tool_call.get("tool")
                    tool_params = tool_call.get("params", {})
                    
                    # LOOP DETECTION
                    import json
                    try:
                        # Create a deterministic signature of the tool call
                        tool_sig = (tool_name, json.dumps(tool_params, sort_keys=True))
                    except:
                        tool_sig = (tool_name, str(tool_params))

                    if tool_sig == last_tool_sig:
                        logger.warning(f"[{self.name}] Detected duplicate tool call loop: {tool_name}")
                        yield {"type": "status", "content": "Skipping duplicate tool call..."}
                        
                        warning_msg = "System: YOU ARE LOOPING. You just executed this exact tool with these exact parameters. STOP. Analyze the previous result and either PROCEED to the next step or output your Final Answer."
                        current_history.append({"role": "system", "content": warning_msg})
                        
                        # Add system event to persist this warning
                        yield {"type": "system", "content": warning_msg}
                        
                        continue
                    
                    last_tool_sig = tool_sig
                    
                    yield {"type": "status", "content": f"Running tool: {tool_name}..."}
                    logger.info(f"[{self.name}] Executing tool: {tool_name}")
                    
                    # Execute
                    try:
                        result_text = ""
                        if tool_name == "run_code":
                            code = tool_params.get("code")
                            if code:
                                res = self.code_executor.execute_code(code)
                                stdout = res.get('stdout', '')
                                stderr = res.get('stderr', '')
                                success = res.get('success', False)
                                
                                if success:
                                    result_text = f"Execution Result:\n{stdout}" if stdout else "Code executed successfully (no output)"
                                else:
                                    result_text = f"Execution Failed:\n{stderr}" if stderr else "Code execution failed"
                            else:
                                result_text = "Error: No 'code' parameter provided for run_code"
                                
                        elif tool_name == "write_file":
                            path = tool_params.get("path")
                            content = tool_params.get("content")
                            if path:
                                full_path = self.code_executor.workspace_path / path
                                full_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(full_path, 'w', encoding='utf-8') as f:
                                    if content is None:
                                         # Handle empty content gracefuly
                                         f.write("")
                                    else:
                                         f.write(content)
                                result_text = f"File {path} written successfully."
                            else:
                                result_text = "Error: Missing path for write_file"
                                
                        elif tool_name == "read_file":
                            path = tool_params.get("path")
                            if path:
                                full_path = self.code_executor.workspace_path / path
                                if full_path.exists():
                                    with open(full_path, 'r', encoding='utf-8') as f:
                                        result_text = f"File Content ({path}):\n{f.read()}"
                                else:
                                    result_text = f"Error: File {path} not found."
                            else:
                                result_text = "Error: Missing path for read_file"
                                
                        elif tool_name == "list_directory":
                            import os
                            files = os.listdir(self.code_executor.workspace_path)
                            result_text = f"Directory listing:\n{', '.join(files)}"
                            
                        else:
                            result_text = f"Error: Unknown tool '{tool_name}'"

                        # Yield log event
                        yield {"type": "log", "content": f"Tool {tool_name} output: {result_text[:200]}..."}
                        
                        # Yield system event for persistency
                        yield {"type": "system", "content": result_text}

                        # Add Result to History
                        current_history.append({"role": "system", "content": result_text})
                        
                        # CONTINUE LOOP -> The agent will see the result in the next turn
                        continue 
                        
                    except Exception as e:
                        err_msg = f"Tool execution error: {e}"
                        logger.error(err_msg)
                        current_history.append({"role": "system", "content": err_msg})
                        yield {"type": "system", "content": err_msg} # Persist error too
                        continue

                else:
                    # No detected tool call. 
                    # CHECK FOR MALFORMED JSON
                    # If the model plainly tried to use a tool (contains "tool": or ```json with "tool")
                    # but our extractor failed, we should warn it.
                    potential_malformed = False
                    lower_text = full_response_text.lower()
                    if '"tool":' in lower_text or "'tool':" in lower_text:
                         potential_malformed = True
                    
                    if potential_malformed:
                        consecutive_malformed_count += 1
                        logger.warning(f"[{self.name}] Detected potential malformed tool call ({consecutive_malformed_count}/3). RAW RESPONSE:\n{full_response_text[:1000]}")
                        
                        if consecutive_malformed_count > 3:
                            err_msg = "[Error: System] Too many formatting errors. Aborting turn to prevent loop."
                            current_history.append({"role": "system", "content": err_msg})
                            yield {"type": "error", "content": err_msg}
                            break
                        
                        # More helpful error message with concrete example
                        err_msg = """⚠️ System: Your last tool call was not valid JSON. Please correct it. REQUIRED FORMAT:

```json
{"tool": "write_file", "params": {"path": "example.py", "content": "print('hello')"}}
```

Do not wrap the JSON in XML tags or other text. Ensure strict JSON syntax."""
                        current_history.append({"role": "system", "content": err_msg})
                        yield {"type": "system", "content": err_msg}
                        yield {"type": "status", "content": "Self-correcting JSON..."}
                        continue

                    # Standard response -> Finish
                    break
                    
            except Exception as e:
                logger.error(f"Error in run_stream: {e}")
                # If we haven't retried too much within this turn (not easy to track here without bigger refactor)
                # For now, just report error.
                error_msg = f"Error: {str(e)}"
                yield {"type": "error", "content": error_msg}
                break

        yield {"type": "status", "content": "Done"}
        logger.info(f"[{self.name}] Stream Complete")

    def _log_llm_request(self, user_input: str, prompt: str):
        """Log the LLM request"""
        logger.info(f"[{self.name}] LLM Request: {user_input}")
    
    def _log_llm_response(self, response: str, success: bool):
        """Log the LLM response"""
        # Log first 1000 chars to debug
        logger.info(f"[{self.name}] LLM Response (Success={success}, Len={len(response)}): {response[:1000]}")

    def _extract_json_tool_call(self, text: str) -> Optional[Dict]:
        """
        Extract JSON tool call from text using robust parsing.
        """
        import json
        import re
        import ast

        # 1. Try to find a code block containing JSON
        # Matches ```json { ... } ``` or just ``` { ... } ```
        code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        
        candidates = []
        if matches:
            candidates.extend(matches)
            
        # 2. If no code blocks, look for any balanced {...} that might be a tool call
        # We search for the outermost braces
        balance = 0
        start = -1
        for i, char in enumerate(text):
            if char == '{':
                if balance == 0:
                    start = i
                balance += 1
            elif char == '}':
                balance -= 1
                if balance == 0 and start != -1:
                    candidates.append(text[start : i+1])
                    start = -1

        # Helper to clean and parse JSON
        def strict_parse(s):
            try:
                return json.loads(s)
            except:
                return None

        def robust_parse(s):
            # 1. Remove comments (// ...)
            s = re.sub(r"//.*", "", s)
            # 2. Remove comments (/* ... */)
            s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
            # 3. Fix trailing commas
            s = re.sub(r",\s*}", "}", s)
            s = re.sub(r",\s*]", "]", s)
            
            # 4. Handle multi-line strings (real newlines in code)
            # This is tricky. We want to convert real newlines inside quotes to \n
            # Regex to find content inside double quotes
            def escape_newlines(m):
                # Replace real newline with \n
                return m.group(0).replace('\n', '\\n').replace('\r', '')
            
            try:
                # Capture encoded strings
                s_fixed = re.sub(r'("(?:[^"\\]|\\.)*")', escape_newlines, s, flags=re.DOTALL)
                return json.loads(s_fixed)
            except:
                pass
            
            # 5. Try ast.literal_eval for Python-style dicts (single quotes)
            try:
                return ast.literal_eval(s)
            except:
                pass

            return None

        # Iterate candidates
        for candidate in candidates:
            # Check if it looks like a tool call
            if "tool" not in candidate and '"tool"' not in candidate and "'tool'" not in candidate:
                continue
                
            # Try strict
            data = strict_parse(candidate)
            if data and isinstance(data, dict) and "tool" in data:
                return data
                
            # Try robust
            data = robust_parse(candidate)
            if data and isinstance(data, dict) and "tool" in data:
                return data

        # 3. Fallback: Regex extraction for specific patterns (last resort)
        # Matches: tool: "name", params: { ... } (keys maybe unquoted)
        try:
            # Look for tool name (key can be "tool" or just tool, value must be quoted)
            tool_match = re.search(r'(?:["\']tool["\']|tool)\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            if tool_match:
                tool_name = tool_match.group(1)
                
                # Look for params block (key "params" or params)
                params_match = re.search(r'(?:["\']params["\']|params)\s*:\s*(\{.*)', text, re.DOTALL | re.IGNORECASE)
                if params_match:
                    params_str_raw = params_match.group(1)
                    # Try to find the matching closing brace for this params block
                    # simple counter
                    p_balance = 0
                    p_end = 0
                    for j, ch in enumerate(params_str_raw):
                        if ch == '{': p_balance += 1
                        elif ch == '}': p_balance -= 1
                        
                        if p_balance == 0:
                            p_end = j + 1
                            break
                    
                    if p_end > 0:
                        params_content = params_str_raw[:p_end]
                        params_data = strict_parse(params_content) or robust_parse(params_content)
                        if params_data:
                            return {"tool": tool_name, "params": params_data}
        except:
            pass
            
        return None

    def _extract_code(self, text: str) -> Optional[str]:
        # Deprecated
        return None


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