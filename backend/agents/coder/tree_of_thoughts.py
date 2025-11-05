"""
Tree of Thoughts реализация для Coder Agent

Позволяет генерировать несколько веток рассуждений
и выбирать лучшее решение.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from backend.core.llm_provider import BaseLLMProvider
from .prompts import (
    get_analyzer_instruction,
    get_solution_instruction,
    get_evaluator_instruction,
    TREE_OF_THOUGHTS_TEMPLATE
)

logger = logging.getLogger(__name__)


@dataclass
class ThoughtBranch:
    """Одна ветка мышления"""
    branch_id: int
    content: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TreeOfThoughtsResult:
    """Результат Tree of Thoughts"""
    task: str
    analysis: str
    branches: List[ThoughtBranch]
    evaluation: str
    best_branch: Optional[ThoughtBranch]
    final_solution: str
    

class TreeOfThoughts:
    """
    Tree of Thoughts для анализа задач программирования
    
    Алгоритм:
    1. Анализ задачи (понимание требований)
    2. Генерация N веток решений параллельно
    3. Оценка каждой ветки
    4. Выбор лучшего решения
    
    Параметры:
        llm_provider: LLM провайдер для генерации
        num_branches: количество веток (по умолчанию 2)
        temperature: температура для разнообразия веток
    """
    
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        num_branches: int = 2,
        temperature: float = 0.7
    ):
        self.llm = llm_provider
        self.num_branches = num_branches
        self.temperature = temperature
    
    def think(self, task: str, context: str = "") -> TreeOfThoughtsResult:
        """
        Запустить Tree of Thoughts для задачи
        
        Args:
            task: Описание задачи
            context: Дополнительный контекст (код, файлы и т.д.)
            
        Returns:
            TreeOfThoughtsResult с анализом и решением
        """
        logger.info(f"ToT: Starting analysis for task: {task[:100]}...")
        
        # Шаг 1: Анализ задачи
        analysis = self._analyze_task(task, context)
        logger.debug(f"ToT: Analysis complete")
        
        # Шаг 2: Генерация веток решений
        branches = self._generate_branches(task, analysis, context)
        logger.debug(f"ToT: Generated {len(branches)} branches")
        
        # Шаг 3: Оценка веток
        evaluation, best_branch = self._evaluate_branches(task, branches)
        logger.debug(f"ToT: Evaluation complete, best branch: {best_branch.branch_id if best_branch else 'None'}")
        
        # Шаг 4: Формирование финального решения
        final_solution = self._extract_final_solution(evaluation, best_branch)
        
        return TreeOfThoughtsResult(
            task=task,
            analysis=analysis,
            branches=branches,
            evaluation=evaluation,
            best_branch=best_branch,
            final_solution=final_solution
        )
    
    def _analyze_task(self, task: str, context: str) -> str:
        """Шаг 1: Анализ задачи"""
        
        prompt = f"""{get_analyzer_instruction()}

## Задача для анализа:
{task}

## Контекст:
{context if context else "Нет дополнительного контекста"}
"""
        
        try:
            response = self.llm.generate(prompt, temperature=0.3)  # Низкая температура для точности
            return response
        except Exception as e:
            logger.error(f"ToT: Error in analysis: {e}")
            return f"Ошибка анализа: {str(e)}"
    
    def _generate_branches(
        self, 
        task: str, 
        analysis: str, 
        context: str
    ) -> List[ThoughtBranch]:
        """Шаг 2: Генерация веток решений"""
        
        branches = []
        
        # Генерируем ветки параллельно для скорости
        def generate_branch(branch_id: int) -> ThoughtBranch:
            prompt = f"""{get_solution_instruction(branch_id)}

## Анализ задачи:
{analysis}

## Оригинальная задача:
{task}

## Контекст:
{context if context else "Нет"}
"""
            
            try:
                # Разная температура для разнообразия
                temp = self.temperature + (branch_id * 0.1)
                response = self.llm.generate(prompt, temperature=min(temp, 1.0))
                return ThoughtBranch(
                    branch_id=branch_id,
                    content=response,
                    metadata={"temperature": temp}
                )
            except Exception as e:
                logger.error(f"ToT: Error generating branch {branch_id}: {e}")
                return ThoughtBranch(
                    branch_id=branch_id,
                    content=f"Ошибка генерации: {str(e)}",
                    score=-1.0
                )
        
        # Параллельная генерация
        with ThreadPoolExecutor(max_workers=self.num_branches) as executor:
            futures = {
                executor.submit(generate_branch, i): i 
                for i in range(1, self.num_branches + 1)
            }
            
            for future in as_completed(futures):
                try:
                    branch = future.result()
                    branches.append(branch)
                except Exception as e:
                    branch_id = futures[future]
                    logger.error(f"ToT: Branch {branch_id} failed: {e}")
        
        # Сортируем по ID для консистентности
        branches.sort(key=lambda x: x.branch_id)
        
        return branches
    
    def _evaluate_branches(
        self, 
        task: str, 
        branches: List[ThoughtBranch]
    ) -> tuple[str, Optional[ThoughtBranch]]:
        """Шаг 3: Оценка веток"""
        
        if not branches:
            return "Нет веток для оценки", None
        
        # Формируем промпт с описанием всех веток
        branches_text = ""
        for branch in branches:
            branches_text += f"\n### Решение {branch.branch_id}\n{branch.content}\n"
        
        prompt = f"""{get_evaluator_instruction()}

## Задача:
{task}

## Предложенные решения:
{branches_text}
"""
        
        try:
            evaluation = self.llm.generate(prompt, temperature=0.2)
            
            # Пытаемся извлечь лучшую ветку из ответа
            best_branch = self._extract_best_branch(evaluation, branches)
            
            # Обновляем score для веток на основе оценки
            self._update_branch_scores(evaluation, branches)
            
            return evaluation, best_branch
            
        except Exception as e:
            logger.error(f"ToT: Error in evaluation: {e}")
            # В случае ошибки возвращаем первую ветку
            return f"Ошибка оценки: {str(e)}", branches[0] if branches else None
    
    def _extract_best_branch(
        self, 
        evaluation: str, 
        branches: List[ThoughtBranch]
    ) -> Optional[ThoughtBranch]:
        """Извлечь рекомендуемую ветку из оценки"""
        
        # Простой поиск по тексту
        import re
        
        # Ищем паттерны типа "Выбрать решение 1" или "решение №2"
        patterns = [
            r"[Вв]ыбрать решение (\d+)",
            r"решение[^\d]*(\d+)",
            r"[Рр]екоменд[а-я]+ решение (\d+)",
            r"[Бб]ест[^\d]*(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, evaluation)
            if match:
                try:
                    branch_id = int(match.group(1))
                    for branch in branches:
                        if branch.branch_id == branch_id:
                            return branch
                except (ValueError, IndexError):
                    continue
        
        # Если не нашли явного указания, берём первую
        return branches[0] if branches else None
    
    def _update_branch_scores(
        self, 
        evaluation: str, 
        branches: List[ThoughtBranch]
    ) -> None:
        """Обновить scores веток на основе оценки"""
        
        import re
        
        # Ищем итоговые баллы типа "Итого: 42/50"
        for branch in branches:
            pattern = rf"Решение {branch.branch_id}.*?[Ии]того[:\s]+(\d+)/50"
            match = re.search(pattern, evaluation, re.DOTALL)
            if match:
                try:
                    branch.score = float(match.group(1)) / 50.0
                except ValueError:
                    pass
    
    def _extract_final_solution(
        self, 
        evaluation: str, 
        best_branch: Optional[ThoughtBranch]
    ) -> str:
        """Извлечь финальный код из оценки или лучшей ветки"""
        
        import re
        
        # Сначала ищем "Финальный код" в evaluation
        pattern = r"[Фф]инальный код.*?```(\w+)?\n(.*?)```"
        match = re.search(pattern, evaluation, re.DOTALL)
        if match:
            return match.group(2).strip()
        
        # Иначе берём код из лучшей ветки
        if best_branch:
            code_pattern = r"```(\w+)?\n(.*?)```"
            matches = re.findall(code_pattern, best_branch.content, re.DOTALL)
            if matches:
                # Берём самый большой блок кода
                best_code = max(matches, key=lambda x: len(x[1]))
                return best_code[1].strip()
        
        return "// Код не найден"


def run_tree_of_thoughts(
    llm_provider: BaseLLMProvider,
    task: str,
    context: str = "",
    num_branches: int = 2
) -> TreeOfThoughtsResult:
    """
    Удобная функция для запуска Tree of Thoughts
    
    Args:
        llm_provider: LLM провайдер
        task: Задача для решения
        context: Дополнительный контекст
        num_branches: Количество веток (по умолчанию 2)
        
    Returns:
        TreeOfThoughtsResult
    """
    tot = TreeOfThoughts(llm_provider, num_branches=num_branches)
    return tot.think(task, context)
