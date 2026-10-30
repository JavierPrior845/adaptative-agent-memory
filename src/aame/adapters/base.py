"""Abstract base class for agent harness transcript adapters.

Enables extensible parsing for Antigravity, Claude Code, Cursor, Cline, and other harnesses.
"""

from __future__ import annotations

import abc
import json
import logging
from pathlib import Path
from typing import Any, Generator, Optional

from aame.core.models import UnifiedSession

logger = logging.getLogger(__name__)


class HarnessAdapter(abc.ABC):
    """Abstract interface for reading and normalizing proprietary agent transcripts."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Identifier name of the harness adapter (e.g. 'antigravity', 'claude_code')."""
        pass

    @abc.abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Check if this adapter recognizes and can parse the given file or directory.
        
        Args:
            path: Path to inspect.
            
        Returns:
            True if compatible, False otherwise.
        """
        pass

    @abc.abstractmethod
    def parse(self, path: Path) -> UnifiedSession:
        """Parse the target transcript file into a normalized UnifiedSession.
        
        Args:
            path: Path to transcript file.
            
        Returns:
            Populated UnifiedSession instance.
            
        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If parsing encounters an unrecoverable format error.
        """
        pass

    @abc.abstractmethod
    def discover_sessions(self, base_dir: Optional[Path] = None) -> list[Path]:
        """Automatically find available session transcripts on the current system.
        
        Args:
            base_dir: Optional custom search root. If None, uses standard harness locations.
            
        Returns:
            List of valid transcript paths found.
        """
        pass

    @staticmethod
    def stream_jsonl(path: Path) -> Generator[dict[str, Any], None, None]:
        """Memory-efficient JSON Lines streaming iterator with error resilience.
        
        Args:
            path: Path to .jsonl file.
            
        Yields:
            Decoded JSON dictionaries for each non-empty valid line.
        """
        if not path.is_file():
            raise FileNotFoundError(f"Transcript file not found: {path}")

        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        yield data
                except json.JSONDecodeError as err:
                    logger.warning("Skipping malformed JSON line %d in %s: %s", line_no, path, err)
