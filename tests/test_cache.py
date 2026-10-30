"""Unit tests for KVCacheAnalyzer."""

from aame.core.cache import KVCacheAnalyzer
from aame.core.models import (
    MessageCategory,
    MessageRole,
    UnifiedMessage,
    UnifiedSession,
)


def test_cache_empty_session():
    analyzer = KVCacheAnalyzer()
    empty = UnifiedSession(session_id="empty", harness_name="test")
    metrics = analyzer.analyze_session(empty)
    assert metrics.total_turns == 0
    assert metrics.estimated_cache_hit_rate == 0.0


def test_cache_single_turn():
    analyzer = KVCacheAnalyzer()
    session = UnifiedSession(
        session_id="single",
        harness_name="test",
        messages=[
            UnifiedMessage(
                id="1",
                step_index=0,
                role=MessageRole.USER,
                category=MessageCategory.USER_INSTRUCTION,
                content="Single instruction",
                token_count=2,
            )
        ],
    )
    metrics = analyzer.analyze_session(session)
    assert metrics.total_turns == 1
    assert metrics.first_divergence_turn is None


def test_cache_append_only_stability(sample_session: UnifiedSession):
    analyzer = KVCacheAnalyzer()
    metrics = analyzer.analyze_session(sample_session)
    assert metrics.total_turns == len(sample_session.messages)
    # Since messages strictly accumulate, prefix should have high retention
    assert metrics.estimated_cache_hit_rate > 0.8
    assert metrics.longest_prefix_tokens > 0
