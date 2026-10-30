"""Agent harness adapters for ingesting conversation logs and transcripts."""

from aame.adapters.base import HarnessAdapter
from aame.adapters.antigravity import AntigravityAdapter

__all__ = [
    "HarnessAdapter",
    "AntigravityAdapter",
]
