"""
Text-based Tool Call Extractor

Многоуровневый парсер для извлечения вызовов инструментов из текста LLM.
Используется как fallback когда модель не поддерживает native tool calling.

Поддерживаемые форматы:
1. XML-like tags: <tool name="write_file">{"path": "..."}</tool>
2. JSON in code blocks: ```json {"tool": "write_file", "params": {...}} ```
3. Markdown actions: **Действие:** write_file **Параметры:** {...}
4. Function call style: write_file({"path": "..."})
5. ReAct format: Action: write_file Action Input: {...}
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .base import ToolCall, ToolCallSource

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Результат попытки извлечения"""
    success: bool
    tool_calls: List[ToolCall]
    pattern_used: Optional[str] = None
    raw_matches: List[Tuple] = None


class ToolCallExtractor:
    """
    Многоуровневый парсер для извлечения tool calls из текста
    
    Использует каскад паттернов от наиболее структурированных
    к наименее, останавливаясь на первом успешном.
    
    Пример использования:
        extractor = ToolCallExtractor()
        calls = extractor.extract(llm_response_text)
        for call in calls:
            result = execute_tool(call.name, call.arguments)
    """
    
    # Паттерны в порядке приоритета (от более надёжных к менее)
    PATTERNS = {
        # 1. XML-like tags (самый надёжный формат)
        "xml_tags": r'<tool\s+name=["\'](\w+)["\'][^>]*>\s*(.*?)\s*</tool>',
        
        # 2. JSON в code block с явным tool
        "json_codeblock_tool": r'```(?:json)?\s*\n\s*\{\s*"tool"\s*:\s*"(\w+)"[^`]*"(?:params|parameters|arguments)"\s*:\s*(\{[^`]+?\})[^`]*\}\s*\n```',
        
        # 3. JSON в code block - весь объект
        "json_codeblock_full": r'```(?:json)?\s*\n(\{[^`]+\})\s*\n```',
        
        # 4. Markdown Actions (русский + английский)
        "markdown_actions": r'\*\*(?:Действие|Action|Tool):\*\*\s*(\w+)\s*\n\*\*(?:Параметры|Parameters|Args|Input):\*\*\s*(?:```(?:json)?\s*)?\s*(\{[\s\S]+?\})\s*(?:```)?',
        
        # 5. ReAct format
        "react_format": r'(?:Action|Tool):\s*(\w+)\s*\n(?:Action Input|Input|Args):\s*(\{[^\n]+\}|\{[\s\S]+?\n\})',
        
        # 6. Function call style: tool_name({...})
        "function_call": r'(\w+)\s*\(\s*(\{[^)]+\})\s*\)',
        
        # 7. Простой JSON с tool полем
        "simple_json_tool": r'\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"(?:params|parameters|arguments)"\s*:\s*(\{[^}]+\})\s*\}',
    }
    
    # Дополнительные паттерны для нестандартных форматов
    FALLBACK_PATTERNS = {
        # Backtick content с multiline (как в проблемном примере)
        "backtick_multiline": r'\*\*(?:Действие|Action):\*\*\s*(\w+)\s*\n\*\*(?:Параметры|Parameters):\*\*\s*\{\s*\n?\s*"path"\s*:\s*"([^"]+)"\s*,\s*\n?\s*"content"\s*:\s*`([\s\S]+?)`\s*\n?\}',
        
        # Backtick content в одну строку
        "backtick_content": r'\*\*(?:Действие|Action):\*\*\s*(\w+)\s*\n\*\*(?:Параметры|Parameters):\*\*\s*\{\s*"path"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*`([^`]+)`',
        
        # Multiline JSON с переносами внутри {}
        "multiline_json": r'\*\*(?:Действие|Action|Tool):\*\*\s*(\w+)\s*\n\*\*(?:Параметры|Parameters|Args):\*\*\s*(\{[\s\S]+?\n\})',
        
        # Простой формат без code blocks
        "simple_action": r'(?:Действие|Action):\s*(\w+)[\s\S]*?(?:Параметры|Parameters|Args):\s*\{([\s\S]*?)\n\}',
        
        # НОВЫЙ: write_file с невалидным JSON (f-strings итд)
        "write_file_broken_json": r'```(?:json)?\s*\{\s*"tool"\s*:\s*"write_file"\s*,\s*"params"\s*:\s*\{\s*"path"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"([\s\S]+?)(?:"\s*\}\s*\}|$)\s*```',
    }
    
    def __init__(self, strict: bool = False):
        """
        Args:
            strict: Если True, не использует fallback паттерны
        """
        self.strict = strict
    
    def extract(self, text: str) -> List[ToolCall]:
        """
        Извлечь все tool calls из текста
        
        Args:
            text: Текст ответа LLM
            
        Returns:
            Список ToolCall объектов
        """
        if not text:
            return []
        
        # Если есть backticks в контексте параметров - сначала пробуем fallback паттерны
        # Это важно для обработки нестандартного формата LLM с `content`
        has_backticks = '`' in text and ('content' in text.lower() or 'path' in text.lower())
        
        if has_backticks and not self.strict:
            for pattern_name, pattern in self.FALLBACK_PATTERNS.items():
                try:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    if matches:
                        calls = self._parse_fallback_matches(matches, pattern_name)
                        if calls and self._has_content(calls):
                            logger.debug(f"Extracted {len(calls)} tool calls using fallback pattern '{pattern_name}'")
                            return calls
                except Exception as e:
                    logger.warning(f"Fallback pattern '{pattern_name}' failed: {e}")
                    continue
        
        # Пробуем основные паттерны
        for pattern_name, pattern in self.PATTERNS.items():
            try:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                if matches:
                    calls = self._parse_matches(matches, pattern_name)
                    if calls:
                        logger.debug(f"Extracted {len(calls)} tool calls using pattern '{pattern_name}'")
                        return calls
            except Exception as e:
                logger.warning(f"Pattern '{pattern_name}' failed: {e}")
                continue
        
        # Финальный fallback
        if not self.strict:
            for pattern_name, pattern in self.FALLBACK_PATTERNS.items():
                try:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    if matches:
                        calls = self._parse_fallback_matches(matches, pattern_name)
                        if calls:
                            logger.debug(f"Extracted {len(calls)} tool calls using fallback pattern '{pattern_name}'")
                            return calls
                except Exception as e:
                    logger.warning(f"Fallback pattern '{pattern_name}' failed: {e}")
                    continue
        
        logger.debug("No tool calls found in text")
        return []
    
    def _has_content(self, calls: List[ToolCall]) -> bool:
        """Проверить, есть ли content в аргументах хоть одного call"""
        for call in calls:
            if 'content' in call.arguments and call.arguments['content']:
                return True
        return False
    
    def extract_with_details(self, text: str) -> ExtractionResult:
        """
        Извлечь tool calls с дополнительной информацией
        
        Returns:
            ExtractionResult с деталями извлечения
        """
        for pattern_name, pattern in self.PATTERNS.items():
            try:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                if matches:
                    calls = self._parse_matches(matches, pattern_name)
                    if calls:
                        return ExtractionResult(
                            success=True,
                            tool_calls=calls,
                            pattern_used=pattern_name,
                            raw_matches=matches
                        )
            except Exception:
                continue
        
        return ExtractionResult(success=False, tool_calls=[], pattern_used=None)
    
    def _parse_matches(self, matches: List[Tuple], pattern_name: str) -> List[ToolCall]:
        """Парсинг совпадений основных паттернов"""
        calls = []
        
        for match in matches:
            try:
                call = self._parse_single_match(match, pattern_name)
                if call:
                    calls.append(call)
            except Exception as e:
                logger.warning(f"Failed to parse match {match[:100] if isinstance(match, str) else match}: {e}")
                continue
        
        return calls
    
    def _parse_single_match(self, match: Tuple, pattern_name: str) -> Optional[ToolCall]:
        """Парсинг одного совпадения"""
        
        if pattern_name == "json_codeblock_full":
            # Весь JSON объект - нужно извлечь tool и params
            json_str = match if isinstance(match, str) else match[0]
            return self._parse_full_json(json_str)
        
        elif pattern_name in ["xml_tags", "json_codeblock_tool", "markdown_actions", 
                              "react_format", "function_call", "simple_json_tool"]:
            # Формат: (tool_name, params_json)
            tool_name = match[0]
            params_str = match[1] if len(match) > 1 else "{}"
            
            arguments = self._parse_json_safe(params_str)
            if arguments is not None:
                return ToolCall(
                    name=tool_name,
                    arguments=arguments,
                    source=ToolCallSource.TEXT_PARSED,
                    raw_text=str(match)
                )
        
        return None
    
    def _parse_fallback_matches(self, matches: List[Tuple], pattern_name: str) -> List[ToolCall]:
        """Парсинг fallback паттернов"""
        calls = []
        
        for match in matches:
            try:
                if pattern_name in ["backtick_content", "backtick_multiline"]:
                    # (tool_name, path, content)
                    tool_name, path, content = match[0], match[1], match[2]
                    calls.append(ToolCall(
                        name=tool_name,
                        arguments={"path": path, "content": content},
                        source=ToolCallSource.TEXT_PARSED,
                        raw_text=str(match)[:200]
                    ))
                    
                elif pattern_name == "multiline_json":
                    # (tool_name, full_json_params)
                    tool_name = match[0]
                    json_str = match[1]
                    
                    # Пробуем парсить JSON, заменяя backticks на обычные кавычки
                    cleaned = re.sub(r'`([^`]+)`', r'"\1"', json_str)
                    arguments = self._parse_json_safe(cleaned)
                    
                    if arguments:
                        calls.append(ToolCall(
                            name=tool_name,
                            arguments=arguments,
                            source=ToolCallSource.TEXT_PARSED,
                            raw_text=str(match)[:200]
                        ))
                    
                elif pattern_name == "simple_action":
                    # (tool_name, params_content без внешних {})
                    tool_name = match[0]
                    params_content = "{" + match[1] + "}"
                    arguments = self._parse_json_safe(params_content)
                    if arguments:
                        calls.append(ToolCall(
                            name=tool_name,
                            arguments=arguments,
                            source=ToolCallSource.TEXT_PARSED,
                            raw_text=str(match)[:200]
                        ))
                
                elif pattern_name == "write_file_broken_json":
                    # (path, content) - специально для сломанного JSON
                    path = match[0]
                    content = match[1]
                    # Декодируем escape-последовательности
                    content = content.replace('\\n', '\n')
                    content = content.replace('\\t', '\t')
                    content = content.replace('\\"', '"')
                    calls.append(ToolCall(
                        name="write_file",
                        arguments={"path": path, "content": content},
                        source=ToolCallSource.TEXT_PARSED,
                        raw_text=f"write_file: {path}"
                    ))
                        
            except Exception as e:
                logger.warning(f"Fallback parse failed for {pattern_name}: {e}")
                continue
        
        return calls
    
    def _parse_full_json(self, json_str: str) -> Optional[ToolCall]:
        """Парсинг полного JSON объекта с tool/params"""
        try:
            data = json.loads(json_str)
            
            # Извлекаем имя инструмента
            tool_name = data.get("tool") or data.get("name") or data.get("function")
            if not tool_name:
                return None
            
            # Извлекаем аргументы
            arguments = (
                data.get("params") or 
                data.get("parameters") or 
                data.get("arguments") or 
                data.get("args") or
                {}
            )
            
            return ToolCall(
                name=tool_name,
                arguments=arguments,
                source=ToolCallSource.TEXT_PARSED,
                raw_text=json_str[:200]
            )
            
        except json.JSONDecodeError:
            return None
    
    def _parse_json_safe(self, json_str: str) -> Optional[Dict[str, Any]]:
        """
        Безопасный парсинг JSON с обработкой распространённых ошибок
        """
        if not json_str:
            return {}
        
        # Очистка строки
        cleaned = json_str.strip()
        
        # Попытка 1: прямой парсинг
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Попытка 2: заменить одинарные кавычки на двойные
        try:
            fixed = cleaned.replace("'", '"')
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # Попытка 3: убрать trailing comma
        try:
            fixed = re.sub(r',\s*}', '}', cleaned)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # Попытка 4: исправить незакавыченные ключи
        try:
            # Простая эвристика для ключей без кавычек
            fixed = re.sub(r'(\w+)\s*:', r'"\1":', cleaned)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # Попытка 5: извлечь key-value pairs вручную
        try:
            return self._extract_key_values(cleaned)
        except Exception:
            pass
        
        logger.warning(f"Failed to parse JSON: {cleaned[:100]}...")
        return None
    
    def _extract_key_values(self, text: str) -> Dict[str, Any]:
        """
        Извлечение key-value пар из текста (последний fallback)
        """
        result = {}
        
        # Паттерн для "key": "value" или "key": value
        pattern = r'"(\w+)"\s*:\s*(?:"([^"]+)"|(\d+(?:\.\d+)?)|(\w+))'
        matches = re.findall(pattern, text)
        
        for key, str_val, num_val, word_val in matches:
            if str_val:
                result[key] = str_val
            elif num_val:
                result[key] = float(num_val) if '.' in num_val else int(num_val)
            elif word_val:
                if word_val.lower() == 'true':
                    result[key] = True
                elif word_val.lower() == 'false':
                    result[key] = False
                elif word_val.lower() == 'null':
                    result[key] = None
                else:
                    result[key] = word_val
        
        return result if result else None


# Глобальный экземпляр для удобства
default_extractor = ToolCallExtractor()


def extract_tool_calls(text: str) -> List[ToolCall]:
    """
    Удобная функция для извлечения tool calls
    
    Args:
        text: Текст ответа LLM
        
    Returns:
        Список ToolCall объектов
    """
    return default_extractor.extract(text)
