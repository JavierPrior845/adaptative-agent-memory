"""Adaptive Agent Memory Engine (AAME).

Deterministic context auditing, token analytics, and memory lifecycle engine
for AI coding agent harnesses.
"""

__version__ = "0.1.0"

from aame.core.models import (
    MessageCategory,
    MessageRole,
    NoiseReport,
    PruningReason,
    UnifiedMessage,
    UnifiedSession,
)
from aame.core.tokenizer import TokenCounter
from aame.core.analyzer import ContextAnalyzer
from aame.core.cache import KVCacheAnalyzer
from aame.adapters.antigravity import AntigravityAdapter

__all__ = [
    "MessageCategory",
    "MessageRole",
    "NoiseReport",
    "PruningReason",
    "UnifiedMessage",
    "UnifiedSession",
    "TokenCounter",
    "ContextAnalyzer",
    "KVCacheAnalyzer",
    "AntigravityAdapter",
]
