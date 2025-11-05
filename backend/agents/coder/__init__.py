"""
Coder Agent - AI ассистент для программирования

Реализует:
- Tree of Thoughts для анализа задач
- Verifier для проверки кода
- Инструменты для работы с файлами
"""

from .agent import create_coder_agent

__all__ = ['create_coder_agent']
