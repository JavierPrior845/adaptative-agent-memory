"""Harness adapter for Anthropic Claude Code session logs.

Claude Code stores session state and conversations in ~/.claude/ or project-local
transcripts (.claude/history.jsonl, session.jsonl).
"""

from __future__ import annotations

import logging
import os
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


class ClaudeCodeAdapter(HarnessAdapter):
    """Parses Claude Code transcript and history logs into UnifiedSession."""

    @property
    def name(self) -> str:
        return "claude_code"

    def can_handle(self, path: Path) -> bool:
        """Check if path is a Claude Code session file or directory."""
        if path.is_file():
            # Matches .claude/history.jsonl or similar transcript files
            return ("claude" in str(path).lower() or ".claude" in path.parts) and path.suffix in (".jsonl", ".json")
        if path.is_dir():
            if path.name == ".claude" or "claude" in path.name.lower():
                return True
            claude_dir = path / ".claude"
            return claude_dir.is_dir()
        return False

    def parse(self, path: Path) -> UnifiedSession:
        """Parse Claude Code session into UnifiedSession."""
        target_file = self._resolve_file_path(path)
        session_id = self._extract_session_id(target_file)

        unified_messages: list[UnifiedMessage] = []
        created_at: Optional[datetime] = None

        for idx, data in enumerate(self.stream_jsonl(target_file)):
            msg = self._normalize_message(data, session_id, idx)
            if msg is not None:
                unified_messages.append(msg)
                if created_at is None and msg.timestamp is not None:
                    created_at = msg.timestamp

        return UnifiedSession(
            session_id=session_id,
            harness_name=self.name,
            source_file=str(target_file),
            messages=unified_messages,
            created_at=created_at,
            metadata={"source": "claude_code", "total_steps": len(unified_messages)},
        )

    def discover_sessions(self, base_dir: Optional[Path] = None) -> list[Path]:
        """Discover Claude Code sessions in ~/.claude/ or workspace."""
        roots_to_check: list[Path] = []
        if base_dir:
            roots_to_check.append(base_dir)
        else:
            home = Path.home()
            roots_to_check.extend([
                home / ".claude" / "sessions",
                home / ".claude" / "projects",
                home / ".claude",
            ])
            # Check local current workspace .claude
            local_claude = Path.cwd() / ".claude"
            if local_claude.is_dir():
                roots_to_check.append(local_claude)

        found: list[Path] = []
        for root in roots_to_check:
            if not root.is_dir():
                continue
            for item in root.rglob("*.jsonl"):
                if item.is_file():
                    found.append(item)

        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def _resolve_file_path(self, path: Path) -> Path:
        """Find the jsonl file inside a directory if a directory was passed."""
        if path.is_dir():
            for name in ("history.jsonl", "transcript.jsonl", "session.jsonl"):
                cand = path / name
                if cand.is_file():
                    return cand
            # Check recursive
            candidates = list(path.glob("*.jsonl"))
            if candidates:
                return candidates[0]
            raise FileNotFoundError(f"No Claude Code transcript file found in: {path}")
        return path

    def _extract_session_id(self, path: Path) -> str:
        """Derive session ID from path."""
        return path.stem.replace(".jsonl", "").replace("history_", "")

    def _normalize_message(self, data: dict[str, Any], session_id: str, step_index: int) -> Optional[UnifiedMessage]:
        """Map Claude Code structure to UnifiedMessage."""
        role_raw = data.get("role") or data.get("type", "unknown")
        content = data.get("content") or data.get("text") or ""
        timestamp_raw = data.get("timestamp") or data.get("created_at")
        tool_use = data.get("tool_use") or data.get("tool_calls")
        tool_name = None
        tool_args = None

        if isinstance(content, list):
            # Claude Code frequently formats content as lists of blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        tool_name = block.get("name")
                        tool_args = block.get("input")
                    elif block.get("type") == "tool_result":
                        text_parts.append(str(block.get("content", "")))
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)

        # Normalize Role and Category
        role_lower = str(role_raw).lower()
        if "user" in role_lower:
            role = MessageRole.USER
            category = MessageCategory.USER_INSTRUCTION
        elif "assistant" in role_lower:
            role = MessageRole.ASSISTANT
            category = MessageCategory.TOOL_CALL if tool_name else MessageCategory.GENERAL
        elif "tool" in role_lower or "result" in role_lower:
            role = MessageRole.TOOL
            category = MessageCategory.TOOL_OUTPUT
        elif "system" in role_lower:
            role = MessageRole.SYSTEM
            category = MessageCategory.SYSTEM_PROMPT
        else:
            role = MessageRole.GENERAL
            category = MessageCategory.GENERAL

        timestamp = None
        if timestamp_raw:
            try:
                timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
            except ValueError:
                pass

        return UnifiedMessage(
            id=f"{session_id}-step-{step_index}",
            step_index=step_index,
            role=role,
            category=category,
            content=content,
            token_count=0,
            is_prunable=False,
            timestamp=timestamp,
            tool_name=tool_name,
            tool_args=tool_args,
            metadata={"raw_role": role_raw},
        )
