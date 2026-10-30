"""Fixtures for AAME test suite."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from aame.core.models import (
    MessageCategory,
    MessageRole,
    UnifiedMessage,
    UnifiedSession,
)
from aame.core.tokenizer import TokenCounter


@pytest.fixture
def token_counter() -> TokenCounter:
    """Fixture providing a initialized TokenCounter."""
    return TokenCounter()


@pytest.fixture
def sample_messages() -> list[UnifiedMessage]:
    """Fixture with a varied sequence of messages."""
    return [
        UnifiedMessage(
            id="s1-msg-0",
            step_index=0,
            role=MessageRole.USER,
            category=MessageCategory.USER_INSTRUCTION,
            content="<USER_REQUEST>Diseña una arquitectura modular para la memoria del agente</USER_REQUEST>",
            token_count=18,
        ),
        UnifiedMessage(
            id="s1-msg-1",
            step_index=1,
            role=MessageRole.ASSISTANT,
            category=MessageCategory.ARCHITECTURE,
            content="Hemos decidido adoptar un diseño desacoplado en frío basado en ficheros para no invalidar el prefix cache.",
            token_count=25,
        ),
        UnifiedMessage(
            id="s1-msg-2",
            step_index=2,
            role=MessageRole.TOOL,
            category=MessageCategory.TOOL_OUTPUT,
            tool_name="view_file",
            content="1: // Long dumped code...\n" * 500,  # Massive output
            token_count=1500,
        ),
        UnifiedMessage(
            id="s1-msg-3",
            step_index=3,
            role=MessageRole.USER,
            category=MessageCategory.SIDE_QUEST,
            content="Oye, ¿cómo funciona exactamente el algoritmo de PageRank en Google?",
            token_count=20,
        ),
        UnifiedMessage(
            id="s1-msg-4",
            step_index=4,
            role=MessageRole.ASSISTANT,
            category=MessageCategory.SIDE_QUEST,
            content="PageRank asigna una puntuación de autoridad a cada página web según la cantidad y calidad de los enlaces...",
            token_count=120,
        ),
    ]


@pytest.fixture
def sample_session(sample_messages: list[UnifiedMessage]) -> UnifiedSession:
    """Fixture providing a populated UnifiedSession."""
    return UnifiedSession(
        session_id="test-session-001",
        harness_name="antigravity",
        messages=sample_messages,
    )


@pytest.fixture
def synthetic_transcript_path(tmp_path: Path) -> Path:
    """Creates a temporary synthetic Antigravity transcript.jsonl file."""
    log_dir = tmp_path / "brain" / "conv-uuid-1234" / ".system_generated" / "logs"
    log_dir.mkdir(parents=True)
    file_path = log_dir / "transcript.jsonl"

    steps = [
        {
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "status": "DONE",
            "created_at": "2026-10-28T12:00:00Z",
            "content": "<USER_REQUEST>Inicializa el proyecto AAME</USER_REQUEST>",
        },
        {
            "step_index": 1,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-28T12:00:05Z",
            "tool_calls": [
                {
                    "name": "run_command",
                    "args": {"CommandLine": "ls -la"},
                }
            ],
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "RUN_COMMAND",
            "status": "DONE",
            "exit_code": 0,
            "created_at": "2026-10-28T12:00:07Z",
            "content": "total 0\ndrwxr-xr-x 2 user user 4096 oct 28 12:00 .\n",
        },
        {
            "step_index": 3,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-28T12:00:10Z",
            "content": "Optamos por una arquitectura de micro-módulos desacoplados.",
        },
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")

    return file_path
