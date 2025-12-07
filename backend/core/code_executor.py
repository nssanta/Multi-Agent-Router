"""
Исполнитель Python кода с поддержкой Sandbox изоляции.

Режимы работы:
1. Sandbox Mode (рекомендуется): Код выполняется в изолированном Docker контейнере
   - Активируется при наличии SANDBOX_URL
   - Безопасное выполнение без доступа к сети
   
2. Local Mode (fallback): Код выполняется локально через subprocess
   - Используется когда sandbox недоступен
   - Менее безопасно, но работает без docker

Особенности:
- Каждая сессия имеет свой workspace
- Timeout protection
- Логирование всех выполнений
"""

import subprocess
import os
import re
from pathlib import Path
from typing import Dict, Optional, List
import logging
import httpx

logger = logging.getLogger(__name__)

# Sandbox URL из переменных окружения
SANDBOX_URL = os.getenv("SANDBOX_URL", "")


class LocalCodeExecutor:
    """
    Исполнитель Python кода с поддержкой Sandbox.
    
    Автоматически выбирает режим:
    - Sandbox если SANDBOX_URL доступен
    - Local subprocess как fallback
    """
    
    def __init__(self, session_path: Path):
        self.session_path = Path(session_path)
        self.workspace_path = self.session_path / "workspace"
        self.logs_path = self.session_path / "logs"
        self.input_path = self.session_path / "input"
        
        # Sandbox configuration
        self.sandbox_url = SANDBOX_URL
        self.use_sandbox = bool(self.sandbox_url) and self._check_sandbox_available()
        
        # Логирование для отладки
        logger.info(f"LocalCodeExecutor initialized:")
        logger.info(f"  session_path: {self.session_path}")
        logger.info(f"  workspace_path: {self.workspace_path}")
        logger.info(f"  sandbox_url: {self.sandbox_url}")
        logger.info(f"  use_sandbox: {self.use_sandbox}")
        
        # Создать директории
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.input_path.mkdir(parents=True, exist_ok=True)
    
    def _check_sandbox_available(self) -> bool:
        """
        Проверяем доступность sandbox service.
        :return: True если доступен
        """
        if not self.sandbox_url:
            return False
        try:
            response = httpx.get(f"{self.sandbox_url}/health", timeout=3)
            available = response.status_code == 200
            logger.info(f"Sandbox health check: {'OK' if available else 'FAILED'}")
            return available
        except Exception as e:
            logger.warning(f"Sandbox not available: {e}")
            return False
    
    def setup_venv(self, force_recreate: bool = False):
        """
        Создаем изолированный venv для сессии.
        :param force_recreate: если True, пересоздаем venv
        """
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
        timeout: int = 60,
        filename: str = "temp_code.py"
    ) -> Dict:
        """
        Выполняем Python код.
        
        Если sandbox доступен — выполняется там (безопасно).
        Иначе — локально через subprocess (fallback).
        
        :param code: Python код для выполнения
        :param timeout: Таймаут в секундах
        :param filename: Имя файла для сохранения кода
        :return: Dict с ключами: returncode, stdout, stderr, success, score
        """
        import time
        from datetime import datetime
        
        # Убрать markdown блоки если есть
        code = code.replace("```python", "").replace("```", "").strip()
        
        # Выбираем режим выполнения
        if self.use_sandbox:
            return self._execute_in_sandbox(code, timeout, filename)
        else:
            return self._execute_locally(code, timeout, filename)
    
    def _execute_in_sandbox(
        self, 
        code: str, 
        timeout: int,
        filename: str
    ) -> Dict:
        """
        Выполняем код в sandbox контейнере через HTTP API.
        :param code: код
        :param timeout: таймаут
        :param filename: имя файла
        :return: результат выполнения
        """
        import time
        from datetime import datetime
        
        logger.info(f"[SANDBOX] Executing code via {self.sandbox_url}")
        start_time = time.time()
        
        try:
            response = httpx.post(
                f"{self.sandbox_url}/execute",
                json={
                    "code": code,
                    "timeout": timeout,
                    "filename": filename
                },
                timeout=timeout + 10  # Extra buffer for network
            )
            
            if response.status_code == 200:
                result = response.json()
                execution_time = time.time() - start_time
                
                success = result.get("success", False)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                
                # Логируем результат
                self._log_execution(
                    filename, code, 
                    {"returncode": result.get("returncode", -1), "stdout": stdout, "stderr": stderr},
                    execution_time=execution_time,
                    score=self._extract_score(stdout),
                    sandbox=True
                )
                
                logger.info(f"[SANDBOX] Execution {'succeeded' if success else 'failed'} in {execution_time:.2f}s")
                
                return {
                    "returncode": result.get("returncode", -1),
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": success,
                    "score": self._extract_score(stdout),
                    "execution_time": execution_time,
                    "sandbox": True
                }
            else:
                error_msg = f"Sandbox error: HTTP {response.status_code}"
                logger.error(error_msg)
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": error_msg,
                    "success": False,
                    "score": None,
                    "sandbox": True
                }
                
        except httpx.TimeoutException:
            execution_time = time.time() - start_time
            error_msg = f"Sandbox timeout ({timeout}s)"
            logger.error(error_msg)
            self._log_execution(filename, code, None, error=error_msg, execution_time=execution_time, sandbox=True)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "success": False,
                "score": None,
                "sandbox": True
            }
        except Exception as e:
            error_msg = f"Sandbox connection error: {e}"
            logger.error(error_msg)
            # Fallback to local execution
            logger.warning("Falling back to local execution")
            return self._execute_locally(code, timeout, filename)
    
    def _execute_locally(
        self, 
        code: str, 
        timeout: int,
        filename: str
    ) -> Dict:
        """
        Выполняем код локально через subprocess (fallback).
        :param code: код
        :param timeout: таймаут
        :param filename: имя файла
        :return: результат выполнения
        """
        import time
        from datetime import datetime
        
        logger.info(f"[LOCAL] Executing code locally")
        
        # Сохранить код в файл
        code_file = self.workspace_path / filename
        logger.info(f"Writing code to: {code_file}")
        code_file.write_text(code, encoding='utf-8')
        
        # Путь к Python - используем системный Python
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
                "score": None,
                "sandbox": False
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
        result: Optional[Dict],
        execution_time: Optional[float] = None,
        score: Optional[float] = None,
        error: Optional[str] = None,
        sandbox: bool = False
    ):
        """
        Логируем выполнение кода в файл.
        :param filename: имя файла
        :param code: код
        :param result: результат выполнения
        :param execution_time: время выполнения
        :param score: оценка
        :param error: ошибка
        :param sandbox: флаг песочницы
        """
        from datetime import datetime
        import json
        
        log_file = self.logs_path / f"code_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "code": code[:2000],  # Limit code size in logs
            "execution_time": execution_time,
            "score": score,
            "mode": "sandbox" if sandbox else "local"
        }
        
        if result:
            if isinstance(result, dict):
                log_data.update({
                    "returncode": result.get("returncode", -1),
                    "stdout": result.get("stdout", "")[:1000],
                    "stderr": result.get("stderr", "")[:1000],
                    "success": result.get("returncode", -1) == 0
                })
            else:
                # subprocess.CompletedProcess
                log_data.update({
                    "returncode": result.returncode,
                    "stdout": result.stdout[:1000] if result.stdout else "",
                    "stderr": result.stderr[:1000] if result.stderr else "",
                    "success": result.returncode == 0
                })
        elif error:
            log_data.update({
                "error": error,
                "success": False
            })
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
    
    def _extract_score(self, stdout: str) -> Optional[float]:
        """
        Извлекаем score из stdout (паттерн: 'Final Validation Performance: X.XXX').
        :param stdout: вывод программы
        :return: оценка или None
        """
        pattern = r"Final Validation Performance:\s*([\d.]+)"
        match = re.search(pattern, stdout)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None
    
    def install_package(self, package: str):
        """
        Устанавливаем пакет в venv.
        :param package: имя пакета
        """
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
        """
        Выполняем Jupyter notebook через nbconvert.
        :param notebook_path: путь к ноутбуку
        :param timeout: таймаут
        :return: результат выполнения
        """
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