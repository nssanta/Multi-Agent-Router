"""
Sandbox Code Executor Service

Isolated FastAPI server for executing Python code securely.
Runs in a separate Docker container with limited resources and no network access.

Security features:
- No network access (network_mode: none in docker-compose)
- Resource limits (CPU, memory)
- Timeout enforcement
- Non-root user
- Read-only filesystem (except /workspace)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import tempfile
import os
import sys
from typing import Optional
from pathlib import Path

app = FastAPI(title="Sandbox Code Executor", version="1.0.0")


class CodeRequest(BaseModel):
    """Request model for code execution"""
    code: str
    timeout: int = 30  # Default 30 seconds
    filename: Optional[str] = "temp_code.py"


class CodeResponse(BaseModel):
    """Response model for code execution"""
    stdout: str
    stderr: str
    returncode: int
    success: bool
    execution_time: Optional[float] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "sandbox"}


@app.post("/execute", response_model=CodeResponse)
async def execute_code(request: CodeRequest):
    """
    Execute Python code in isolated environment.
    
    Args:
        request: CodeRequest with code to execute
        
    Returns:
        CodeResponse with stdout, stderr, returncode
    """
    import time
    
    # Validate timeout (max 5 minutes)
    timeout = min(request.timeout, 300)
    
    # Clean code (remove markdown blocks if present)
    code = request.code.replace("```python", "").replace("```", "").strip()
    
    # Write code to workspace
    workspace = Path("/workspace")
    workspace.mkdir(exist_ok=True)
    
    code_file = workspace / request.filename
    code_file.write_text(code, encoding='utf-8')
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, str(code_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workspace),
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(workspace),
                "HOME": "/home/sandbox"
            }
        )
        
        execution_time = time.time() - start_time
        
        return CodeResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            success=result.returncode == 0,
            execution_time=execution_time
        )
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return CodeResponse(
            stdout="",
            stderr=f"Execution timeout ({timeout}s)",
            returncode=-1,
            success=False,
            execution_time=execution_time
        )
    except Exception as e:
        return CodeResponse(
            stdout="",
            stderr=str(e),
            returncode=-1,
            success=False
        )
    finally:
        # Cleanup
        try:
            code_file.unlink(missing_ok=True)
        except:
            pass


@app.post("/install")
async def install_package(package: str):
    """
    Install a Python package (limited functionality).
    For security, only allow specific packages.
    """
    # Whitelist of allowed packages
    allowed = {"numpy", "pandas", "matplotlib", "scipy", "scikit-learn"}
    
    if package.lower() not in allowed:
        raise HTTPException(
            status_code=403, 
            detail=f"Package {package} not in whitelist. Allowed: {allowed}"
        )
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", package],
            capture_output=True,
            text=True,
            timeout=120
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
