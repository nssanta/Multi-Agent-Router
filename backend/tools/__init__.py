"""Tools for AI agents - web search, content reading, file operations, etc."""

from .web_search import duckduckgo_search, format_search_results
from .smart_search import smart_search, format_smart_results
from .web_reader import read_url, read_multiple_urls, format_read_results, get_web_reader

# Модульная система инструментов
from .base import BaseTool, ToolResult, ToolRegistry, tool_registry, register_tool
from .file_tools import ReadFileTool, WriteFileTool, ListDirTool, DiffTool, ApplyDiffTool

# Notebook инструменты
from .notebook_tools import (
    NotebookListCellsTool,
    NotebookReadCellTool,
    NotebookAddCellTool,
    NotebookUpdateCellTool,
    NotebookDeleteCellTool,
    NotebookSearchTool,
    NotebookCreateTool,
    NotebookDiffTool,
)

__all__ = [
    # Веб-поиск
    'duckduckgo_search',
    'format_search_results',
    'smart_search',
    'format_smart_results',
    'read_url',
    'read_multiple_urls',
    'format_read_results',
    'get_web_reader',
    # Модульные инструменты
    'BaseTool',
    'ToolResult',
    'ToolRegistry',
    'tool_registry',
    'register_tool',
    'ReadFileTool',
    'WriteFileTool',
    'ListDirTool',
    'DiffTool',
    'ApplyDiffTool',
    # Notebook инструменты
    'NotebookListCellsTool',
    'NotebookReadCellTool',
    'NotebookAddCellTool',
    'NotebookUpdateCellTool',
    'NotebookDeleteCellTool',
    'NotebookSearchTool',
    'NotebookCreateTool',
    'NotebookDiffTool',
]
