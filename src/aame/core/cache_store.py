"""Session cache manager for AAME.

Provides lightweight, incremental local caching of analyzed session metrics,
token counts, and category classifications to eliminate redundant parsing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from aame.core.models import MessageCategory, MessageRole, PruningReason, UnifiedMessage, UnifiedSession
from aame.utils.paths import get_global_config_dir

logger = logging.getLogger(__name__)


class SessionCache:
    """Manages persistent disk caching of analyzed conversation steps."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """Initialize session cache.
        
        Args:
            cache_dir: Optional custom directory. Defaults to ~/.config/aame/cache
        """
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = get_global_config_dir() / "cache"

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create cache directory %s: %s", self.cache_dir, exc)

    def _get_cache_file(self, session_id: str) -> Path:
        """Return path to cache JSON for given session ID."""
        return self.cache_dir / f"{session_id}.json"

    def get_cached_session(self, session_id: str, transcript_mtime: Optional[float] = None) -> Optional[dict[str, Any]]:
        """Retrieve cached metadata if valid and not superseded by transcript updates.
        
        Args:
            session_id: Session identifier.
            transcript_mtime: Modification timestamp of original transcript file.
            
        Returns:
            Dict of cached steps or None if miss / stale.
        """
        cache_file = self._get_cache_file(session_id)
        if not cache_file.is_file():
            return None

        try:
            with cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if transcript_mtime is not None:
                cached_mtime = data.get("transcript_mtime", 0.0)
                if transcript_mtime > cached_mtime:
                    # Transcript was modified after cache was created
                    return None

            return data
        except Exception as exc:
            logger.debug("Error reading cache for session %s: %s", session_id, exc)
            return None

    def save_session(
        self,
        session: UnifiedSession,
        transcript_mtime: Optional[float] = None,
    ) -> bool:
        """Serialize analyzed session metrics to cache.
        
        Args:
            session: UnifiedSession instance.
            transcript_mtime: Mtime of source transcript.
            
        Returns:
            True if cached successfully, False otherwise.
        """
        cache_file = self._get_cache_file(session.session_id)
        try:
            serialized_messages = []
            for msg in session.messages:
                serialized_messages.append({
                    "step_index": msg.step_index,
                    "token_count": msg.token_count,
                    "category": msg.category.value,
                    "is_prunable": msg.is_prunable,
                    "pruning_reason": msg.pruning_reason.value if msg.pruning_reason else None,
                })

            payload = {
                "session_id": session.session_id,
                "harness_name": session.harness_name,
                "transcript_mtime": transcript_mtime or 0.0,
                "total_tokens": session.total_tokens,
                "prunable_tokens": session.prunable_tokens,
                "steps": serialized_messages,
            }

            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return True
        except Exception as exc:
            logger.warning("Failed to write session cache: %s", exc)
            return False

    def clear(self) -> int:
        """Clear all cached sessions. Returns number of removed files."""
        count = 0
        if self.cache_dir.is_dir():
            for p in self.cache_dir.glob("*.json"):
                try:
                    p.unlink()
                    count += 1
                except OSError:
                    pass
        return count
