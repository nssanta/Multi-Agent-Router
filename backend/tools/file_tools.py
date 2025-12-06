"""
Инструменты для работы с файлами

Инструменты:
- ReadFileTool: чтение файлов
- WriteFileTool: запись/создание файлов
- ListDirTool: листинг директорий
- DiffTool: создание diff между версиями
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import difflib
import os
import logging

from .base import BaseTool, ToolResult, register_tool

logger = logging.getLogger(__name__)


@register_tool
class ReadFileTool(BaseTool):
    """Чтение содержимого файла"""
    
    name = "read_file"
    description = "Прочитать содержимое файла по указанному пути. Возвращает текст файла."
    parameters = {
        "path": {
            "type": "string",
            "description": "Путь к файлу (относительно session workspace или абсолютный)"
        },
        "start_line": {
            "type": "integer",
            "description": "Начальная строка (опционально, 1-indexed)"
        },
        "end_line": {
            "type": "integer",
            "description": "Конечная строка (опционально, 1-indexed)"
        }
    }
    required_params = ["path"]
    agent_types = ["coder", "mle", "ds", "all"]
    
    def execute(
        self, 
        path: str, 
        start_line: Optional[int] = None, 
        end_line: Optional[int] = None
    ) -> ToolResult:
        """Прочитать файл"""
        try:
            # Резолвим путь относительно session_path если есть
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return ToolResult.error(f"File not found: {path}")
            
            if not file_path.is_file():
                return ToolResult.error(f"Not a file: {path}")
            
            # Читаем файл
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # Применяем фильтр по строкам
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else total_lines
                lines = lines[start_idx:end_idx]
            
            content = "".join(lines)
            
            return ToolResult.success(
                data=content,
                message=f"Read {len(lines)} lines from {path}",
                metadata={
                    "path": str(file_path),
                    "total_lines": total_lines,
                    "lines_returned": len(lines)
                }
            )
            
        except Exception as e:
            logger.exception(f"Error reading file {path}")
            return ToolResult.error(f"Error reading file: {str(e)}")
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь относительно workspace сессии"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            # Пробуем в workspace сессии
            workspace = Path(self.session_path) / "workspace"
            candidate = workspace / path
            if candidate.exists():
                return candidate
            # Пробуем в input
            input_dir = Path(self.session_path) / "input"
            candidate = input_dir / path
            if candidate.exists():
                return candidate
            # Возвращаем workspace версию по умолчанию
            return workspace / path
        return p


@register_tool
class WriteFileTool(BaseTool):
    """Запись/создание файла"""
    
    name = "write_file"
    description = "Записать содержимое в файл. Создаст файл если не существует."
    parameters = {
        "path": {
            "type": "string",
            "description": "Путь к файлу (относительно session workspace)"
        },
        "file_path": {
            "type": "string",
            "description": "Альтернативное имя для path (для совместимости)"
        },
        "content": {
            "type": "string",
            "description": "Содержимое для записи"
        },
        "mode": {
            "type": "string",
            "enum": ["write", "append"],
            "description": "Режим записи: 'write' (перезапись) или 'append' (добавление)"
        }
    }
    required_params = ["content"]  # path или file_path
    agent_types = ["coder", "mle", "ds"]
    
    def execute(
        self, 
        path: str = None,
        file_path: str = None,  # Alias для совместимости с разными LLM
        content: str = "",
        mode: str = "write",
        **kwargs  # Игнорируем лишние параметры
    ) -> ToolResult:
        """Записать файл"""
        try:
            # Поддержка alias file_path
            actual_path = path or file_path
            if not actual_path:
                return ToolResult.error("Missing required parameter: path or file_path")
            
            # Декодируем escape-последовательности в content
            # LLM часто передаёт \\n вместо реальных newlines
            if isinstance(content, str):
                # Заменяем литеральные escape-последовательности на реальные
                content = content.replace('\\n', '\n')
                content = content.replace('\\t', '\t')
                content = content.replace('\\r', '\r')
                content = content.replace('\\"', '"')
                content = content.replace("\\'", "'")
            
            # Резолвим путь
            resolved_path = self._resolve_path(actual_path)
            
            # Создаём директории если нужно
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Записываем
            write_mode = "w" if mode == "write" else "a"
            with open(resolved_path, write_mode, encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult.success(
                data={"path": str(resolved_path), "bytes_written": len(content)},
                message=f"Successfully wrote {len(content)} characters to {actual_path}"
            )
            
        except Exception as e:
            logger.exception(f"Error writing file {actual_path}")
            return ToolResult.error(f"Error writing file: {str(e)}")
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь в workspace сессии"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            return Path(self.session_path) / "workspace" / path
        return p


@register_tool
class ListDirTool(BaseTool):
    """Листинг директории"""
    
    name = "list_directory"
    description = "Получить список файлов и папок в директории."
    parameters = {
        "path": {
            "type": "string",
            "description": "Путь к директории"
        },
        "recursive": {
            "type": "boolean",
            "description": "Рекурсивный обход (по умолчанию False)"
        },
        "include_hidden": {
            "type": "boolean", 
            "description": "Включить скрытые файлы (по умолчанию False)"
        }
    }
    required_params = ["path"]
    agent_types = ["coder", "mle", "ds", "all"]
    
    def execute(
        self, 
        path: str, 
        recursive: bool = False,
        include_hidden: bool = False
    ) -> ToolResult:
        """Получить листинг директории"""
        try:
            dir_path = self._resolve_path(path)
            
            if not dir_path.exists():
                return ToolResult.error(f"Directory not found: {path}")
            
            if not dir_path.is_dir():
                return ToolResult.error(f"Not a directory: {path}")
            
            items = []
            
            if recursive:
                iterator = dir_path.rglob("*")
            else:
                iterator = dir_path.iterdir()
            
            for item in iterator:
                # Пропускаем скрытые если не нужны
                if not include_hidden and item.name.startswith("."):
                    continue
                
                try:
                    stat = item.stat()
                    items.append({
                        "name": item.name,
                        "path": str(item.relative_to(dir_path)),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": stat.st_mtime
                    })
                except (PermissionError, OSError):
                    continue
            
            # Сортируем: папки первые, потом по имени
            items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            
            return ToolResult.success(
                data=items,
                message=f"Found {len(items)} items in {path}",
                metadata={"total_items": len(items)}
            )
            
        except Exception as e:
            logger.exception(f"Error listing directory {path}")
            return ToolResult.error(f"Error listing directory: {str(e)}")
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            workspace = Path(self.session_path) / "workspace"
            if path == "." or path == "":
                return workspace
            return workspace / path
        return p


@register_tool
class DiffTool(BaseTool):
    """Создание и применение diff"""
    
    name = "diff"
    description = "Создать unified diff между двумя версиями текста или файлов."
    parameters = {
        "original": {
            "type": "string",
            "description": "Оригинальный текст или путь к файлу"
        },
        "modified": {
            "type": "string",
            "description": "Изменённый текст или путь к файлу"
        },
        "is_file": {
            "type": "boolean",
            "description": "True если original/modified это пути к файлам"
        },
        "context_lines": {
            "type": "integer",
            "description": "Количество строк контекста (по умолчанию 3)"
        }
    }
    required_params = ["original", "modified"]
    agent_types = ["coder"]
    
    def execute(
        self, 
        original: str, 
        modified: str, 
        is_file: bool = False,
        context_lines: int = 3
    ) -> ToolResult:
        """Создать diff"""
        try:
            # Получаем содержимое
            if is_file:
                orig_path = self._resolve_path(original)
                mod_path = self._resolve_path(modified)
                
                if not orig_path.exists():
                    return ToolResult.error(f"Original file not found: {original}")
                if not mod_path.exists():
                    return ToolResult.error(f"Modified file not found: {modified}")
                
                with open(orig_path, "r", encoding="utf-8") as f:
                    orig_lines = f.readlines()
                with open(mod_path, "r", encoding="utf-8") as f:
                    mod_lines = f.readlines()
                
                from_file = original
                to_file = modified
            else:
                orig_lines = original.splitlines(keepends=True)
                mod_lines = modified.splitlines(keepends=True)
                from_file = "original"
                to_file = "modified"
            
            # Создаём unified diff
            diff = list(difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=from_file,
                tofile=to_file,
                n=context_lines
            ))
            
            diff_text = "".join(diff)
            
            if not diff_text:
                return ToolResult.success(
                    data="",
                    message="No differences found"
                )
            
            # Считаем изменения
            additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
            deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
            
            return ToolResult.success(
                data=diff_text,
                message=f"+{additions}/-{deletions} lines changed",
                metadata={
                    "additions": additions,
                    "deletions": deletions
                }
            )
            
        except Exception as e:
            logger.exception("Error creating diff")
            return ToolResult.error(f"Error creating diff: {str(e)}")
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            return Path(self.session_path) / "workspace" / path
        return p


@register_tool
class ApplyDiffTool(BaseTool):
    """Применение diff к файлу"""
    
    name = "apply_diff"
    description = "Применить unified diff к файлу для внесения изменений."
    parameters = {
        "path": {
            "type": "string",
            "description": "Путь к файлу для изменения"
        },
        "diff": {
            "type": "string",
            "description": "Unified diff для применения"
        }
    }
    required_params = ["path", "diff"]
    agent_types = ["coder"]
    
    def execute(self, path: str, diff: str) -> ToolResult:
        """Применить diff к файлу"""
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return ToolResult.error(f"File not found: {path}")
            
            # Читаем текущее содержимое
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            
            # Парсим diff и применяем (упрощённая версия)
            # Для production нужна более robust реализация
            new_content = self._apply_unified_diff(original_content, diff)
            
            if new_content is None:
                return ToolResult.error("Failed to apply diff - patch does not match")
            
            # Записываем результат
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            return ToolResult.success(
                data={"path": str(file_path)},
                message=f"Successfully applied diff to {path}"
            )
            
        except Exception as e:
            logger.exception(f"Error applying diff to {path}")
            return ToolResult.error(f"Error applying diff: {str(e)}")
    
    def _apply_unified_diff(self, original: str, diff_text: str) -> Optional[str]:
        """Применить unified diff (упрощённая реализация)"""
        # Используем простой подход: парсим hunks и применяем
        lines = original.splitlines(keepends=True)
        diff_lines = diff_text.splitlines(keepends=True)
        
        result = []
        line_idx = 0
        diff_idx = 0
        
        while diff_idx < len(diff_lines):
            line = diff_lines[diff_idx]
            
            # Пропускаем заголовки
            if line.startswith("---") or line.startswith("+++"):
                diff_idx += 1
                continue
            
            # Парсим hunk header
            if line.startswith("@@"):
                # @@ -start,count +start,count @@
                import re
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    orig_start = int(match.group(1)) - 1
                    
                    # Добавляем строки до начала hunk
                    while line_idx < orig_start and line_idx < len(lines):
                        result.append(lines[line_idx])
                        line_idx += 1
                
                diff_idx += 1
                continue
            
            # Обрабатываем содержимое hunk
            if line.startswith("+"):
                # Добавление
                result.append(line[1:])
                diff_idx += 1
            elif line.startswith("-"):
                # Удаление - пропускаем строку из оригинала
                line_idx += 1
                diff_idx += 1
            elif line.startswith(" "):
                # Контекст
                result.append(lines[line_idx] if line_idx < len(lines) else line[1:])
                line_idx += 1
                diff_idx += 1
            else:
                diff_idx += 1
        
        # Добавляем оставшиеся строки
        while line_idx < len(lines):
            result.append(lines[line_idx])
            line_idx += 1
        
        return "".join(result)
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            return Path(self.session_path) / "workspace" / path
        return p


@register_tool
class RunCodeTool(BaseTool):
    """Выполнение Python кода"""
    
    name = "run_code"
    description = "Выполнить Python код и получить результат. Используется для тестирования и вычислений."
    parameters = {
        "code": {
            "type": "string",
            "description": "Python код для выполнения"
        },
        "timeout": {
            "type": "integer",
            "description": "Таймаут в секундах (по умолчанию 30)"
        }
    }
    required_params = ["code"]
    agent_types = ["coder", "mle", "ds"]
    
    def execute(self, code: str, timeout: int = 30, **kwargs) -> ToolResult:
        """Выполнить Python код"""
        import subprocess
        import sys
        import tempfile
        import re
        
        try:
            # Умная обработка: если передана shell команда вместо Python кода
            code = code.strip()
            
            # Паттерн для "python file.py" или "python3 file.py"
            shell_pattern = r'^python[3]?\s+([^\s]+\.py)(?:\s+(.*))?$'
            match = re.match(shell_pattern, code)
            if match:
                filename = match.group(1)
                args = match.group(2) or ''
                # Преобразуем в Python exec
                if args:
                    code = f"import sys; sys.argv = ['{filename}', '{args}']; exec(open('{filename}').read())"
                else:
                    code = f"exec(open('{filename}').read())"
            
            # Создаём временный файл
            with tempfile.NamedTemporaryFile(
                mode="w", 
                suffix=".py", 
                delete=False,
                encoding="utf-8"
            ) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Выполняем код
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self._get_working_dir()
                )
                
                output = result.stdout
                error = result.stderr
                exit_code = result.returncode
                
                if exit_code == 0:
                    return ToolResult.success(
                        data={
                            "output": output,
                            "exit_code": exit_code
                        },
                        message=f"Code executed successfully",
                        metadata={"stderr": error} if error else {}
                    )
                else:
                    return ToolResult.error(
                        f"Code failed with exit code {exit_code}",
                        data={
                            "output": output,
                            "error": error,
                            "exit_code": exit_code
                        }
                    )
                    
            finally:
                # Удаляем временный файл
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return ToolResult.error(f"Code execution timed out after {timeout} seconds")
        except Exception as e:
            logger.exception("Error executing code")
            return ToolResult.error(f"Error executing code: {str(e)}")
    
    def _get_working_dir(self) -> str:
        """Получить рабочую директорию"""
        if self.session_path:
            workspace = Path(self.session_path) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            return str(workspace)
        return os.getcwd()


@register_tool
class SearchFilesTool(BaseTool):
    """Поиск по содержимому файлов"""
    
    name = "search_files"
    description = "Поиск текста или паттерна в файлах. Возвращает совпадения с контекстом."
    parameters = {
        "pattern": {
            "type": "string",
            "description": "Текст или regex паттерн для поиска"
        },
        "path": {
            "type": "string",
            "description": "Директория для поиска (по умолчанию workspace)"
        },
        "file_pattern": {
            "type": "string",
            "description": "Glob паттерн для фильтра файлов (например *.py)"
        },
        "is_regex": {
            "type": "boolean",
            "description": "Интерпретировать pattern как regex (по умолчанию False)"
        }
    }
    required_params = ["pattern"]
    agent_types = ["coder", "mle", "ds"]
    
    def execute(
        self, 
        pattern: str, 
        path: str = ".",
        file_pattern: str = "*",
        is_regex: bool = False,
        **kwargs
    ) -> ToolResult:
        """Поиск в файлах"""
        import re
        import fnmatch
        
        try:
            search_dir = self._resolve_path(path)
            
            if not search_dir.exists():
                return ToolResult.error(f"Directory not found: {path}")
            
            # Компилируем паттерн
            if is_regex:
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                except re.error as e:
                    return ToolResult.error(f"Invalid regex pattern: {e}")
            else:
                # Экранируем для literal search
                regex = re.compile(re.escape(pattern), re.IGNORECASE)
            
            matches = []
            files_searched = 0
            
            # Ищем файлы
            for file_path in search_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                
                # Проверяем glob фильтр
                if file_pattern != "*" and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue
                
                # Пропускаем бинарные файлы
                if self._is_binary(file_path):
                    continue
                
                files_searched += 1
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    
                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append({
                                "file": str(file_path.relative_to(search_dir)),
                                "line": line_num,
                                "content": line.rstrip()[:200],  # Ограничиваем
                                "context_before": lines[max(0, line_num-2):line_num-1] if line_num > 1 else [],
                                "context_after": lines[line_num:min(len(lines), line_num+1)]
                            })
                            
                            # Ограничиваем количество совпадений
                            if len(matches) >= 50:
                                break
                    
                    if len(matches) >= 50:
                        break
                        
                except Exception:
                    continue
            
            if not matches:
                return ToolResult.success(
                    data=[],
                    message=f"No matches found in {files_searched} files"
                )
            
            return ToolResult.success(
                data=matches,
                message=f"Found {len(matches)} matches in {files_searched} files",
                metadata={
                    "files_searched": files_searched,
                    "match_count": len(matches)
                }
            )
            
        except Exception as e:
            logger.exception("Error searching files")
            return ToolResult.error(f"Error searching files: {str(e)}")
    
    def _is_binary(self, file_path: Path) -> bool:
        """Проверить, является ли файл бинарным"""
        binary_extensions = {
            '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin',
            '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg',
            '.mp3', '.mp4', '.avi', '.mkv', '.wav',
            '.zip', '.tar', '.gz', '.rar', '.7z',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',
            '.woff', '.woff2', '.ttf', '.eot'
        }
        return file_path.suffix.lower() in binary_extensions
    
    def _resolve_path(self, path: str) -> Path:
        """Резолвим путь"""
        p = Path(path)
        if p.is_absolute():
            return p
        if self.session_path:
            workspace = Path(self.session_path) / "workspace"
            if path == "." or path == "":
                return workspace
            return workspace / path
        return p
