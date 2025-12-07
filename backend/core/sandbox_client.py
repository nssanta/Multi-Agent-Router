"""
Sandbox Client для безопасного выполнения кода.

Общается с изолированным sandbox контейнером через HTTP API.
Обеспечивает:
- Изоляция выполнения кода от основного backend
- Ресурсные лимиты (CPU, память)
- Timeout protection
- Логирование
"""

import httpx
import logging
import os
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class SandboxClient:
    """
    Клиент для sandbox code executor service.
    
    Использует HTTP API для выполнения кода в изолированном контейнере.
    """
    
    def __init__(
        self, 
        sandbox_url: Optional[str] = None,
        session_path: Optional[Path] = None
    ):
        """
        Args:
            sandbox_url: URL sandbox service (default: from env)
            session_path: Path к сессии для логирования
        """
        self.sandbox_url = sandbox_url or os.getenv("SANDBOX_URL", "http://sandbox:8001")
        self.session_path = Path(session_path) if session_path else None
        
        if self.session_path:
            self.workspace_path = self.session_path / "workspace"
            self.logs_path = self.session_path / "logs"
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            self.logs_path.mkdir(parents=True, exist_ok=True)
        else:
            self.workspace_path = Path("/workspace")
            self.logs_path = None
        
        logger.info(f"SandboxClient initialized: {self.sandbox_url}")
    
    async def execute_code_async(
        self, 
        code: str, 
        timeout: int = 60,
        filename: str = "temp_code.py"
    ) -> Dict:
        """
        Асинхронно выполняет Python код в sandbox.
        
        Args:
            code: Python код для выполнения
            timeout: Таймаут в секундах
            filename: Имя файла для сохранения кода
        
        Returns:
            Dict с ключами: returncode, stdout, stderr, success, execution_time
        """
        import time
        
        # Убрать markdown блоки если есть
        code = code.replace("```python", "").replace("```", "").strip()
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=timeout + 10) as client:
                response = await client.post(
                    f"{self.sandbox_url}/execute",
                    json={
                        "code": code,
                        "timeout": timeout,
                        "filename": filename
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Логируем
                    self._log_execution(filename, code, result)
                    
                    return {
                        "returncode": result.get("returncode", -1),
                        "stdout": result.get("stdout", ""),
                        "stderr": result.get("stderr", ""),
                        "success": result.get("success", False),
                        "score": self._extract_score(result.get("stdout", "")),
                        "execution_time": result.get("execution_time")
                    }
                else:
                    error_msg = f"Sandbox error: {response.status_code}"
                    logger.error(error_msg)
                    return {
                        "returncode": -1,
                        "stdout": "",
                        "stderr": error_msg,
                        "success": False,
                        "score": None
                    }
                    
        except httpx.TimeoutException:
            error_msg = f"Sandbox timeout ({timeout}s)"
            logger.error(error_msg)
            self._log_execution(filename, code, None, error=error_msg)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "success": False,
                "score": None
            }
        except Exception as e:
            error_msg = f"Sandbox connection error: {e}"
            logger.error(error_msg)
            self._log_execution(filename, code, None, error=error_msg)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "success": False,
                "score": None
            }
    
    def execute_code(
        self, 
        code: str, 
        timeout: int = 60,
        filename: str = "temp_code.py"
    ) -> Dict:
        """
        Синхронно выполняет Python код в sandbox.
        
        Обертка над async версией для обратной совместимости.
        """
        import asyncio
        
        # Проверяем, есть ли уже event loop
        try:
            loop = asyncio.get_running_loop()
            # Если есть loop, используем asyncio.run в новом потоке
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    self.execute_code_async(code, timeout, filename)
                )
                return future.result()
        except RuntimeError:
            # Нет running loop, создаём новый
            return asyncio.run(self.execute_code_async(code, timeout, filename))
    
    def is_available(self) -> bool:
        """Проверяет доступность sandbox service."""
        try:
            import httpx
            response = httpx.get(f"{self.sandbox_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _extract_score(self, stdout: str) -> Optional[float]:
        """Извлекаем score из stdout."""
        import re
        pattern = r"Final Validation Performance:\s*([\d.]+)"
        match = re.search(pattern, stdout)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None
    
    def _log_execution(
        self,
        filename: str,
        code: str,
        result: Optional[Dict],
        error: Optional[str] = None
    ):
        """Логируем выполнение кода."""
        if not self.logs_path:
            return
        
        log_file = self.logs_path / f"sandbox_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "code": code[:1000],  # Limit code size in logs
            "sandbox_url": self.sandbox_url
        }
        
        if result:
            log_data.update({
                "returncode": result.get("returncode"),
                "stdout": result.get("stdout", "")[:500],
                "stderr": result.get("stderr", "")[:500],
                "success": result.get("success"),
                "execution_time": result.get("execution_time")
            })
        elif error:
            log_data.update({"error": error, "success": False})
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
