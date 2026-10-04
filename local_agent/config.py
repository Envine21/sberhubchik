"""Единая конфигурация агента: лимиты, таймауты, workspace, история."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from .workspace import Workspace


@dataclass
class Config:
    max_steps: int = 8
    model_timeout: float = 30.0
    tool_timeout: float = 5.0
    workspace: Optional[Workspace] = None
    log_events: bool = False
    history_turns: int = 0  # <-- ВАЖНО: добавлено поле для памяти

    @classmethod
    def from_env(cls, workspace_root: Path) -> "Config":
        """Создать конфигурацию, считав настройки из переменных окружения."""
        max_steps = int(os.environ.get("AGENT_MAX_STEPS", "8"))
        model_timeout = float(os.environ.get("AGENT_MODEL_TIMEOUT", "30.0"))
        tool_timeout = float(os.environ.get("AGENT_TOOL_TIMEOUT", "5.0"))
        log_events = os.environ.get("AGENT_LOG_EVENTS", "").lower() in ("1", "true", "yes")
        history_turns = int(os.environ.get("HISTORY_TURNS", "0"))  # <-- ВАЖНО: читаем из env
        
        return cls(
            max_steps=max_steps,
            model_timeout=model_timeout,
            tool_timeout=tool_timeout,
            log_events=log_events,
            history_turns=history_turns,
        )

    def bind_workspace(self, root: Path) -> None:
        """Зафиксировать корень workspace. Вызывается один раз при старте."""
        if self.workspace is not None:
            raise RuntimeError("Workspace уже зафиксирован; повторный вызов bind_workspace запрещён")
        self.workspace = Workspace(root)