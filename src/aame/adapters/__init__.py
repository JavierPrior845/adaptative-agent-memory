"""Agent harness adapters for ingesting conversation logs and transcripts."""

from aame.adapters.base import HarnessAdapter
from aame.adapters.antigravity import AntigravityAdapter
from aame.adapters.claude_code import ClaudeCodeAdapter

__all__ = [
    "HarnessAdapter",
    "AntigravityAdapter",
    "ClaudeCodeAdapter",
]
