"""Adapter for Google Antigravity IDE agent session transcripts.

Parses transcript.jsonl files located in:
<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from aame.adapters.base import HarnessAdapter
from aame.core.models import (
    MessageCategory,
    MessageRole,
    UnifiedMessage,
    UnifiedSession,
)

logger = logging.getLogger(__name__)


class AntigravityAdapter(HarnessAdapter):
    """Parses Antigravity IDE transcript.jsonl and discovers local brain sessions."""

    @property
    def name(self) -> str:
        return "antigravity"

    def can_handle(self, path: Path) -> bool:
        """Verify if the path is an Antigravity transcript or session folder."""
        if path.is_file():
            return "transcript" in path.name and path.suffix == ".jsonl"
        if path.is_dir():
            target = path / ".system_generated" / "logs" / "transcript.jsonl"
            return target.is_file()
        return False

    def parse(self, path: Path) -> UnifiedSession:
        """Parse Antigravity JSONL transcript into UnifiedSession."""
        transcript_file = self._resolve_file_path(path)
        session_id = self._extract_session_id(transcript_file)

        unified_messages: list[UnifiedMessage] = []
        created_at: Optional[datetime] = None

        for data in self.stream_jsonl(transcript_file):
            msg = self._normalize_step(data, session_id)
            if msg is not None:
                unified_messages.append(msg)
                if created_at is None and msg.timestamp is not None:
                    created_at = msg.timestamp

        return UnifiedSession(
            session_id=session_id,
            harness_name=self.name,
            source_file=str(transcript_file),
            messages=unified_messages,
            created_at=created_at,
            metadata={"total_steps": len(unified_messages)},
        )

    def discover_sessions(self, base_dir: Optional[Path] = None) -> list[Path]:
        """Discover all available Antigravity brain sessions on the local system."""
        roots_to_check = []
        if base_dir:
            roots_to_check.append(base_dir)
        else:
            # Check default locations
            home = Path.home()
            roots_to_check.extend([
                home / ".gemini" / "antigravity-ide" / "brain",
                home / ".antigravity" / "brain",
            ])
            # Windows AppData fallback
            appdata = os.environ.get("APPDATA")
            if appdata:
                roots_to_check.append(Path(appdata) / "antigravity-ide" / "brain")

        found_transcripts: list[Path] = []
        for root in roots_to_check:
            if not root.is_dir():
                continue
            for conv_dir in root.iterdir():
                if not conv_dir.is_dir():
                    continue
                log_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
                if log_file.is_file():
                    found_transcripts.append(log_file)

        # Sort newest first based on mtime
        found_transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found_transcripts

    def _resolve_file_path(self, path: Path) -> Path:
        """Resolve directory or file path to the exact transcript.jsonl file."""
        if path.is_dir():
            candidate = path / ".system_generated" / "logs" / "transcript.jsonl"
            if candidate.is_file():
                return candidate
            full_candidate = path / ".system_generated" / "logs" / "transcript_full.jsonl"
            if full_candidate.is_file():
                return full_candidate
            raise FileNotFoundError(f"No transcript.jsonl found in Antigravity session directory: {path}")
        return path

    def _extract_session_id(self, path: Path) -> str:
        """Extract conversation UUID from the parent directory hierarchy."""
        # Typically .../brain/<conversation-id>/.system_generated/logs/transcript.jsonl
        parts = path.parts
        if ".system_generated" in parts:
            idx = parts.index(".system_generated")
            if idx > 0:
                return parts[idx - 1]
        return path.stem

    def _normalize_step(self, step_data: dict[str, Any], session_id: str) -> Optional[UnifiedMessage]:
        """Convert a single Antigravity JSON object into a UnifiedMessage."""
        step_index = step_data.get("step_index", 0)
        source = step_data.get("source", "UNKNOWN")
        step_type = step_data.get("type", "UNKNOWN")
        content = step_data.get("content") or ""
        created_at_raw = step_data.get("created_at")
        exit_code = step_data.get("exit_code")

        timestamp = None
        if created_at_raw:
            try:
                # Handle ISO timestamps like 2026-10-21T18:00:22Z
                timestamp = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        msg_id = f"{session_id}-step-{step_index}"

        # Determine Role and Category
        role = MessageRole.SYSTEM
        category = MessageCategory.GENERAL
        tool_name = None
        tool_args = None

        if source == "USER_EXPLICIT" or step_type == "USER_INPUT":
            role = MessageRole.USER
            category = MessageCategory.USER_INSTRUCTION

        elif source == "SYSTEM" or step_type in ("CONVERSATION_HISTORY", "KNOWLEDGE_ARTIFACTS"):
            role = MessageRole.SYSTEM
            category = MessageCategory.SYSTEM_PROMPT

        elif step_type == "PLANNER_RESPONSE":
            role = MessageRole.ASSISTANT
            tool_calls = step_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                first_tool = tool_calls[0]
                tool_name = first_tool.get("name")
                tool_args = first_tool.get("args")
                category = MessageCategory.TOOL_CALL
            else:
                category = MessageCategory.GENERAL

        elif step_type in ("RUN_COMMAND", "VIEW_FILE", "GREP_SEARCH", "LIST_DIR", "READ_URL_CONTENT"):
            role = MessageRole.TOOL
            tool_name = step_type.lower()
            if exit_code is not None and exit_code != 0:
                category = MessageCategory.ERROR
            else:
                category = MessageCategory.TOOL_OUTPUT

        elif source == "MODEL":
            role = MessageRole.ASSISTANT
            category = MessageCategory.GENERAL

        else:
            role = MessageRole.SYSTEM
            category = MessageCategory.GENERAL

        return UnifiedMessage(
            id=msg_id,
            step_index=step_index,
            role=role,
            category=category,
            content=content,
            token_count=0,  # Will be calculated by TokenCounter
            is_prunable=False,
            pruning_reason=None,
            timestamp=timestamp,
            tool_name=tool_name,
            tool_args=tool_args,
            exit_code=exit_code,
            metadata={
                "source": source,
                "type": step_type,
                "status": step_data.get("status"),
                "truncated": step_data.get("is_truncated", False),
            },
        )
