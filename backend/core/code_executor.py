"""
Локальный исполнитель Python кода в изолированном venv.
Заменяет VertexAiCodeExecutor из Google ADK.

Особенности:
- Каждая сессия имеет свой venv
- Код выполняется через subprocess
- Timeout protection
- Установка пакетов в venv
"""

import subprocess
import os
import re
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class LocalCodeExecutor:
    """Исполнитель Python кода в изолированном окружении"""
    
    def __init__(self, session_path: Path):
        self.session_path = Path(session_path)
        self.venv_path = self.session_path / ".venv"
        self.workspace_path = self.session_path / "workspace"
        self.logs_path = self.session_path / "logs"
        self.input_path = self.session_path / "input"
        
        # Логирование для отладки
        logger.info(f"LocalCodeExecutor initialized:")
        logger.info(f"  session_path: {self.session_path}")
        logger.info(f"  workspace_path: {self.workspace_path}")
        
        # Создать директории
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.input_path.mkdir(parents=True, exist_ok=True)
    
    def setup_venv(self, force_recreate: bool = False):
        """Создаем изолированный venv для сессии."""
        if self.venv_path.exists() and not force_recreate:
            logger.info(f"Venv already exists: {self.venv_path}")
            return
        
        logger.info(f"Creating venv: {self.venv_path}")
        
        # Создать venv
        subprocess.run(
            ["python3", "-m", "venv", str(self.venv_path)],
            check=True,
            capture_output=True
        )
        
        # Обновить pip
        pip_path = self.venv_path / "bin" / "pip"
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            check=True,
            capture_output=True
        )
        
        # Установить базовые пакеты
        base_packages = [
            "pandas", "numpy", "matplotlib", "scikit-learn",
            "seaborn", "jupyter", "nbformat", "nbconvert",
            "scipy", "xgboost", "lightgbm", "catboost"
        ]
        
        logger.info(f"Installing packages: {base_packages}")
        subprocess.run(
            [str(pip_path), "install"] + base_packages,
            check=True,
            capture_output=True
        )
        
        logger.info("Venv setup complete")
    
    def execute_code(
        self, 
        code: str, 
        timeout: int = 600,
        filename: str = "temp_code.py"
    ) -> Dict:
        """
        Выполняем Python код в изолированном окружении.
        
        Args:
            code: Python код для выполнения
            timeout: Таймаут в секундах
            filename: Имя файла для сохранения кода
        
        Returns:
            Dict с ключами:
                - returncode: код возврата
                - stdout: вывод stdout
                - stderr: вывод stderr
                - success: успешность выполнения
                - score: извлеченный score (если есть)
        """
        import time
        from datetime import datetime
        
        # Убрать markdown блоки если есть
        code = code.replace("```python", "").replace("```", "").strip()
        
        # Сохранить код в файл
        code_file = self.workspace_path / filename
        logger.info(f"Writing code to: {code_file}")
        code_file.write_text(code, encoding='utf-8')
        
        # Путь к Python - сначала пробуем venv, потом системный
        python_path = self.venv_path / "bin" / "python"
        
        if not python_path.exists():
            # Fallback на системный Python
            import shutil
            system_python = shutil.which("python3") or shutil.which("python")
            if system_python:
                python_path = Path(system_python)
                logger.info(f"Using system Python: {python_path}")
            else:
                error_msg = "Python not found"
                logger.error(error_msg)
                self._log_execution(filename, code, None, error=error_msg)
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": error_msg,
                    "success": False,
                    "score": None
                }
        
        logger.info(f"Executing code file: {filename}")
        logger.info(f"  code_file (full): {code_file}")
        logger.info(f"  cwd: {self.workspace_path}")
        logger.info(f"  python_path: {python_path}")
        start_time = time.time()
        
        try:
            # Запустить код
            cmd = [str(python_path), str(code_file)]
            logger.info(f"  Command: {cmd}")
            result = subprocess.run(
                cmd,
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONPATH": str(self.workspace_path)}
            )
            
            execution_time = time.time() - start_time
            
            # Извлечь score из stdout (если есть паттерн "Final Validation Performance: X.XXX")
            score = self._extract_score(result.stdout)
            
            success = result.returncode == 0
            
            # Логировать результат
            self._log_execution(
                filename, 
                code, 
                result, 
                execution_time=execution_time,
                score=score
            )
            
            logger.info(f"Code execution {'succeeded' if success else 'failed'} in {execution_time:.2f}s")
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": success,
                "score": score,
                "execution_time": execution_time
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Execution timeout ({timeout}s)"
            logger.error(error_msg)
            self._log_execution(filename, code, None, error=error_msg, execution_time=execution_time)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "success": False,
                "score": None
            }
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Code execution error: {error_msg}")
            self._log_execution(filename, code, None, error=error_msg, execution_time=execution_time)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "success": False,
                "score": None
            }
    
    def _log_execution(
        self,
        filename: str,
        code: str,
        result: Optional[subprocess.CompletedProcess],
        execution_time: Optional[float] = None,
        score: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Логируем выполнение кода в файл."""
        from datetime import datetime
        import json
        
        log_file = self.logs_path / f"code_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "code": code,
            "execution_time": execution_time,
            "score": score
        }
        
        if result:
            log_data.update({
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            })
        elif error:
            log_data.update({
                "error": error,
                "success": False
            })
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    def _extract_score(self, stdout: str) -> Optional[float]:
        """Извлекаем score из stdout (паттерн: 'Final Validation Performance: X.XXX')."""
        pattern = r"Final Validation Performance:\s*([\d.]+)"
        match = re.search(pattern, stdout)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None
    
    def install_package(self, package: str):
        """Устанавливаем пакет в venv."""
        pip_path = self.venv_path / "bin" / "pip"
        subprocess.run(
            [str(pip_path), "install", package],
            check=True,
            capture_output=True
        )
        logger.info(f"Installed package: {package}")
    
    def execute_jupyter_notebook(
        self, 
        notebook_path: Path, 
        timeout: int = 600
    ) -> Dict:
        """Выполняем Jupyter notebook через nbconvert."""
        python_path = self.venv_path / "bin" / "python"
        nbconvert_path = self.venv_path / "bin" / "jupyter"
        
        try:
            result = subprocess.run(
                [
                    str(nbconvert_path), "nbconvert",
                    "--to", "notebook",
                    "--execute",
                    "--inplace",
                    str(notebook_path)
                ],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Notebook execution timeout ({timeout}s)",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }