"""
Управление сессиями агентов

Каждая сессия:
- Имеет уникальный ID
- Принадлежит определенному агенту (dialog/mle/ds)
- Имеет изолированный workspace с venv
- Сохраняет историю диалога
- Логирует все действия
"""

import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Менеджер сессий агентов"""
    
    def __init__(self, workspace_dir: str = "./workspace/sessions"):
        # Преобразуем в абсолютный путь
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(
        self,
        agent_type: str,
        user_id: str = "default",
        initial_files: Optional[List[Path]] = None,
        model_id: Optional[str] = None,
    ) -> Dict:
        """
        Создаем новую сессию.
        
        Args:
            agent_type: Тип агента (dialog/mle/ds)
            user_id: ID пользователя
            initial_files: Список файлов для копирования в input/
        
        Returns:
            Dict с session_id и path
        """
        session_id = str(uuid.uuid4())
        session_path = self.workspace_dir / agent_type / session_id
        
        # Создать структуру
        (session_path / "input").mkdir(parents=True)
        (session_path / "workspace").mkdir()
        (session_path / "logs").mkdir()
        
        # Скопировать initial files
        if initial_files:
            for file_path in initial_files:
                dest = session_path / "input" / file_path.name
                shutil.copy2(file_path, dest)
                logger.info(f"Copied {file_path} to {dest}")
        
        # Создать history.json
        history = {
            "session_id": session_id,
            "agent_type": agent_type,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "state": {},
        }

        # Привязать модель к сессии, если указана
        if model_id:
            history["state"]["model_id"] = model_id
        
        with open(session_path / "history.json", "w") as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"Created session {session_id} for {agent_type}")
        
        return {
            "session_id": session_id,
            "path": str(session_path),
            "agent_type": agent_type
        }
    
    def get_session(self, session_id: str, agent_type: str) -> Dict:
        """Получаем сессию по ID."""
        session_path = self.workspace_dir / agent_type / session_id
        
        if not session_path.exists():
            raise ValueError(f"Session {session_id} not found")
        
        with open(session_path / "history.json") as f:
            history = json.load(f)
        
        # Вернуть данные из history напрямую + path для внутреннего использования
        return {
            **history,  # распаковать все поля из history
            "path": str(session_path)
        }
    
    def add_message(
        self, 
        session_id: str, 
        agent_type: str,
        role: str, 
        content: str,
        files: Optional[List[str]] = None
    ):
        """Добавляем сообщение в историю."""
        session_path = self.workspace_dir / agent_type / session_id
        history_file = session_path / "history.json"
        
        with open(history_file) as f:
            history = json.load(f)
        
        history["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "files": files or []
        })
        
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    
    def update_state(
        self, 
        session_id: str, 
        agent_type: str,
        state_updates: Dict
    ):
        """Обновляем state сессии."""
        session_path = self.workspace_dir / agent_type / session_id
        history_file = session_path / "history.json"
        
        with open(history_file) as f:
            history = json.load(f)
        
        history["state"].update(state_updates)
        
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    
    def list_sessions(self, agent_type: Optional[str] = None) -> List[Dict]:
        """Получаем список всех сессий."""
        sessions = []
        
        if agent_type:
            agent_dirs = [self.workspace_dir / agent_type]
        else:
            agent_dirs = [d for d in self.workspace_dir.iterdir() if d.is_dir()]
        
        for agent_dir in agent_dirs:
            if not agent_dir.exists():
                continue
                
            for session_dir in agent_dir.iterdir():
                if session_dir.is_dir():
                    history_file = session_dir / "history.json"
                    if history_file.exists():
                        with open(history_file) as f:
                            history = json.load(f)
                        sessions.append({
                            "session_id": history["session_id"],
                            "agent_type": history["agent_type"],
                            "created_at": history["created_at"],
                            "message_count": len(history["messages"])
                        })
        
        return sessions
    
    def delete_session(self, session_id: str, agent_type: str):
        """Удаляем сессию."""
        session_path = self.workspace_dir / agent_type / session_id
        
        if session_path.exists():
            shutil.rmtree(session_path)
            logger.info(f"Deleted session {session_id}")