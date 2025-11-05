"""
Verifier Agent для проверки кода

Проверяет:
- Синтаксис
- Логику
- Edge cases
- Безопасность
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import logging
import ast
import re

from backend.core.llm_provider import BaseLLMProvider
from .prompts import get_verifier_instruction

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Статус верификации"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class IssueSeverity(str, Enum):
    """Серьёзность проблемы"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Issue:
    """Найденная проблема"""
    severity: IssueSeverity
    message: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class VerificationResult:
    """Результат верификации кода"""
    status: VerificationStatus
    issues: List[Issue]
    llm_analysis: str
    summary: str
    code_is_valid: bool


class CodeVerifier:
    """
    Верификатор кода
    
    Выполняет проверки:
    1. Статический анализ (синтаксис Python)
    2. LLM анализ (логика, security, etc.)
    
    Параметры:
        llm_provider: LLM для анализа
        verifier_model_id: ID модели для верификатора (None = та же модель)
    """
    
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        verifier_model_id: Optional[str] = None
    ):
        self.llm = llm_provider
        self.verifier_model_id = verifier_model_id
        # TODO: если verifier_model_id указан, создать отдельный провайдер
    
    def verify(
        self, 
        code: str, 
        language: str = "python",
        context: str = ""
    ) -> VerificationResult:
        """
        Проверить код
        
        Args:
            code: Код для проверки
            language: Язык программирования
            context: Дополнительный контекст (задача, требования)
            
        Returns:
            VerificationResult
        """
        logger.info(f"Verifier: Starting verification for {language} code")
        
        issues: List[Issue] = []
        
        # Шаг 1: Статический анализ (для Python)
        if language.lower() == "python":
            syntax_issues = self._check_python_syntax(code)
            issues.extend(syntax_issues)
        
        # Шаг 2: Базовые проверки безопасности
        security_issues = self._check_basic_security(code, language)
        issues.extend(security_issues)
        
        # Шаг 3: LLM анализ
        llm_analysis = self._llm_analyze(code, language, context)
        llm_issues = self._parse_llm_issues(llm_analysis)
        issues.extend(llm_issues)
        
        # Определяем статус
        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == IssueSeverity.HIGH for i in issues)
        
        if has_critical:
            status = VerificationStatus.FAILED
            code_is_valid = False
        elif has_high:
            status = VerificationStatus.WARNING
            code_is_valid = True  # Можно использовать с осторожностью
        else:
            status = VerificationStatus.PASSED
            code_is_valid = True
        
        # Формируем summary
        summary = self._generate_summary(status, issues)
        
        return VerificationResult(
            status=status,
            issues=issues,
            llm_analysis=llm_analysis,
            summary=summary,
            code_is_valid=code_is_valid
        )
    
    def _check_python_syntax(self, code: str) -> List[Issue]:
        """Проверить синтаксис Python"""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(Issue(
                severity=IssueSeverity.CRITICAL,
                message=f"Синтаксическая ошибка: {e.msg}",
                line=e.lineno,
                suggestion="Исправьте синтаксис в указанной строке"
            ))
        
        return issues
    
    def _check_basic_security(self, code: str, language: str) -> List[Issue]:
        """Базовые проверки безопасности"""
        issues = []
        
        # Опасные паттерны для Python
        dangerous_patterns = [
            (r'\beval\s*\(', "Использование eval() - потенциальная уязвимость"),
            (r'\bexec\s*\(', "Использование exec() - потенциальная уязвимость"),
            (r'__import__\s*\(', "Динамический импорт может быть опасен"),
            (r'subprocess\.call\s*\(.+shell\s*=\s*True', "shell=True в subprocess опасен"),
            (r'os\.system\s*\(', "os.system() опасен, используйте subprocess"),
            (r'pickle\.loads?\s*\(', "pickle небезопасен для непроверенных данных"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                # Находим номер строки
                for i, line in enumerate(code.split('\n'), 1):
                    if re.search(pattern, line):
                        issues.append(Issue(
                            severity=IssueSeverity.HIGH,
                            message=message,
                            line=i,
                            suggestion="Рассмотрите более безопасную альтернативу"
                        ))
                        break
        
        return issues
    
    def _llm_analyze(self, code: str, language: str, context: str) -> str:
        """LLM анализ кода"""
        
        prompt = f"""{get_verifier_instruction()}

## Язык:
{language}

## Код для проверки:
```{language}
{code}
```

## Контекст (задача):
{context if context else "Не указан"}
"""
        
        try:
            response = self.llm.generate(prompt, temperature=0.2)
            return response
        except Exception as e:
            logger.error(f"Verifier: LLM analysis failed: {e}")
            return f"LLM анализ не удался: {str(e)}"
    
    def _parse_llm_issues(self, analysis: str) -> List[Issue]:
        """Извлечь issues из LLM анализа"""
        issues = []
        
        # Ищем проблемы по паттернам
        severity_map = {
            "CRITICAL": IssueSeverity.CRITICAL,
            "HIGH": IssueSeverity.HIGH,
            "MEDIUM": IssueSeverity.MEDIUM,
            "LOW": IssueSeverity.LOW,
        }
        
        # Паттерн: [SEVERITY] описание проблемы
        pattern = r'\[(CRITICAL|HIGH|MEDIUM|LOW)\][:\s]+(.+?)(?=\n\[|$)'
        matches = re.findall(pattern, analysis, re.IGNORECASE | re.DOTALL)
        
        for severity_str, message in matches:
            severity = severity_map.get(severity_str.upper(), IssueSeverity.MEDIUM)
            issues.append(Issue(
                severity=severity,
                message=message.strip()
            ))
        
        # Также ищем нумерованные списки проблем
        list_pattern = r'\d+\.\s+\*?\*?(CRITICAL|HIGH|MEDIUM|LOW)\*?\*?[:\s-]+(.+?)(?=\n\d+\.|$)'
        list_matches = re.findall(list_pattern, analysis, re.IGNORECASE | re.DOTALL)
        
        for severity_str, message in list_matches:
            severity = severity_map.get(severity_str.upper(), IssueSeverity.MEDIUM)
            # Проверяем что не дубликат
            if not any(i.message == message.strip() for i in issues):
                issues.append(Issue(
                    severity=severity,
                    message=message.strip()
                ))
        
        return issues
    
    def _generate_summary(self, status: VerificationStatus, issues: List[Issue]) -> str:
        """Сгенерировать краткое резюме"""
        
        if status == VerificationStatus.PASSED:
            return "✅ Код прошёл верификацию. Критических проблем не обнаружено."
        
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
        medium_count = sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM)
        
        parts = []
        if critical_count:
            parts.append(f"{critical_count} критических")
        if high_count:
            parts.append(f"{high_count} высоких")
        if medium_count:
            parts.append(f"{medium_count} средних")
        
        issues_text = ", ".join(parts) if parts else "нет"
        
        if status == VerificationStatus.FAILED:
            return f"❌ Верификация провалена. Найдено проблем: {issues_text}"
        else:
            return f"⚠️ Код требует внимания. Найдено проблем: {issues_text}"


def verify_code(
    llm_provider: BaseLLMProvider,
    code: str,
    language: str = "python",
    context: str = "",
    verifier_model_id: Optional[str] = None
) -> VerificationResult:
    """
    Удобная функция для верификации кода
    
    Args:
        llm_provider: LLM провайдер
        code: Код для проверки
        language: Язык программирования
        context: Контекст задачи
        verifier_model_id: ID модели для верификатора
        
    Returns:
        VerificationResult
    """
    verifier = CodeVerifier(llm_provider, verifier_model_id)
    return verifier.verify(code, language, context)
