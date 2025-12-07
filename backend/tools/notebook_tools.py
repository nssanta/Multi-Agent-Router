"""
Инструменты для редактирования Jupyter Notebooks.
Интеграция notebook_editor.py как части модульной системы tools.
"""
import subprocess
import json
import os
from pathlib import Path
from typing import Optional, List
from .base import BaseTool, ToolResult, register_tool


@register_tool
class NotebookListCellsTool(BaseTool):
    """Показать список ячеек в Jupyter notebook."""
    
    name = "notebook_list_cells"
    description = "Показать список ячеек в Jupyter notebook файле (.ipynb). Возвращает индекс, тип и превью каждой ячейки."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "limit": {
            "type": "integer",
            "description": "Максимальное количество ячеек для показа (0 = все)",
            "required": False
        }
    }

    def execute(self, notebook_path: str, limit: int = 0) -> ToolResult:
        """
        Показываем список ячеек в Jupyter notebook.
        :param notebook_path: путь к файлу
        :param limit: лимит ячеек
        :return: результат выполнения
        """
        try:
            # notebook_editor.py теперь в том же каталоге
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = ["python", str(editor_path), "list", notebook_path]
            if limit > 0:
                cmd.extend(["--limit", str(limit)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookReadCellTool(BaseTool):
    """Прочитать содержимое ячейки из Jupyter notebook."""
    
    name = "notebook_read_cell"
    description = "Прочитать содержимое конкретной ячейки из Jupyter notebook по её индексу."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "cell_index": {
            "type": "integer",
            "description": "Индекс ячейки (начиная с 0)",
            "required": True
        }
    }

    def execute(self, notebook_path: str, cell_index: int) -> ToolResult:
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = ["python", str(editor_path), "read", notebook_path, str(cell_index)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookAddCellTool(BaseTool):
    """Добавить новую ячейку в Jupyter notebook."""
    
    name = "notebook_add_cell"
    description = "Добавить новую ячейку (code или markdown) в Jupyter notebook."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "content": {
            "type": "string",
            "description": "Содержимое ячейки",
            "required": True
        },
        "cell_type": {
            "type": "string",
            "description": "Тип ячейки: 'code' или 'markdown'",
            "required": False
        },
        "index": {
            "type": "integer",
            "description": "Позиция для вставки (-1 = в конец)",
            "required": False
        }
    }

    def execute(self, notebook_path: str, content: str, cell_type: str = "code", index: int = -1) -> ToolResult:
        """
        Добавляем новую ячейку в Jupyter notebook.
        :param notebook_path: путь к файлу
        :param content: содержимое ячейки
        :param cell_type: тип ячейки
        :param index: индекс вставки
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = [
                "python", str(editor_path), "add", notebook_path,
                "--type", cell_type,
                "--index", str(index),
                "--content", content
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookUpdateCellTool(BaseTool):
    """Обновить содержимое ячейки в Jupyter notebook."""
    
    name = "notebook_update_cell"
    description = "Обновить содержимое существующей ячейки в Jupyter notebook."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "cell_index": {
            "type": "integer",
            "description": "Индекс ячейки для обновления",
            "required": True
        },
        "content": {
            "type": "string",
            "description": "Новое содержимое ячейки",
            "required": True
        }
    }

    def execute(self, notebook_path: str, cell_index: int, content: str) -> ToolResult:
        """
        Обновляем содержимое ячейки в Jupyter notebook.
        :param notebook_path: путь к файлу
        :param cell_index: индекс ячейки
        :param content: новое содержимое
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = [
                "python", str(editor_path), "update", notebook_path,
                str(cell_index),
                "--content", content
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookDeleteCellTool(BaseTool):
    """Удалить ячейку из Jupyter notebook."""
    
    name = "notebook_delete_cell"
    description = "Удалить ячейку из Jupyter notebook по её индексу."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "cell_index": {
            "type": "integer",
            "description": "Индекс ячейки для удаления",
            "required": True
        }
    }

    def execute(self, notebook_path: str, cell_index: int) -> ToolResult:
        """
        Удаляем ячейку из Jupyter notebook.
        :param notebook_path: путь к файлу
        :param cell_index: индекс ячейки
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = ["python", str(editor_path), "delete", notebook_path, str(cell_index)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool  
class NotebookSearchTool(BaseTool):
    """Поиск в Jupyter notebook."""
    
    name = "notebook_search"
    description = "Искать текст во всех ячейках Jupyter notebook."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "query": {
            "type": "string",
            "description": "Поисковый запрос",
            "required": True
        },
        "use_regex": {
            "type": "boolean",
            "description": "Использовать regex",
            "required": False
        }
    }

    def execute(self, notebook_path: str, query: str, use_regex: bool = False) -> ToolResult:
        """
        Ищем текст в Jupyter notebook.
        :param notebook_path: путь к файлу
        :param query: поисковый запрос
        :param use_regex: использовать regex
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = ["python", str(editor_path), "search", notebook_path, query]
            if use_regex:
                cmd.append("--regex")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookCreateTool(BaseTool):
    """Создать новый Jupyter notebook."""
    
    name = "notebook_create"
    description = "Создать новый пустой Jupyter notebook файл."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь для нового .ipynb файла",
            "required": True
        }
    }

    def execute(self, notebook_path: str) -> ToolResult:
        """
        Создаем новый Jupyter notebook.
        :param notebook_path: путь к файлу
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = ["python", str(editor_path), "create", notebook_path]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")


@register_tool
class NotebookDiffTool(BaseTool):
    """Показать различия между текущей ячейкой и новым содержимом."""
    
    name = "notebook_diff"
    description = "Показать diff (различия) между текущим содержимым ячейки и предлагаемым новым содержимым. Полезно перед обновлением ячейки."
    
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Путь к .ipynb файлу",
            "required": True
        },
        "cell_index": {
            "type": "integer",
            "description": "Индекс ячейки",
            "required": True
        },
        "new_content": {
            "type": "string",
            "description": "Новое содержимое для сравнения",
            "required": True
        }
    }

    def execute(self, notebook_path: str, cell_index: int, new_content: str) -> ToolResult:
        """
        Показываем diff между текущей ячейкой и новым содержимым.
        :param notebook_path: путь к файлу
        :param cell_index: индекс ячейки
        :param new_content: новое содержимое
        :return: результат выполнения
        """
        try:
            editor_path = Path(__file__).parent / "notebook_editor.py"
            cmd = [
                "python", str(editor_path), "diff", notebook_path,
                str(cell_index),
                "--content", new_content
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return ToolResult(success=False, data=None, error=result.stderr or "Unknown error")
            
            return ToolResult(success=True, data=result.stdout.strip(), error=None)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data=None, error="Timeout: операция заняла слишком долго")
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Error: {str(e)}")
