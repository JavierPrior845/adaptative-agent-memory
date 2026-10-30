"""Unit tests for Pydantic unified models."""

from aame.core.models import (
    MessageCategory,
    MessageRole,
    PruningReason,
    UnifiedMessage,
    UnifiedSession,
)


def test_unified_message_creation():
    msg = UnifiedMessage(
        id="test-1",
        step_index=0,
        role=MessageRole.USER,
        category=MessageCategory.USER_INSTRUCTION,
        content="Hello world",
        token_count=3,
    )
    assert msg.id == "test-1"
    assert msg.role == MessageRole.USER
    assert not msg.is_prunable
    assert msg.pruning_reason is None


def test_unified_message_pruning_mark():
    msg = UnifiedMessage(
        id="test-2",
        step_index=1,
        role=MessageRole.TOOL,
        category=MessageCategory.TOOL_OUTPUT,
        content="Massive dump...",
        token_count=1000,
    )
    msg.mark_prunable(PruningReason.MASSIVE_TOOL_OUTPUT)
    assert msg.is_prunable
    assert msg.pruning_reason == PruningReason.MASSIVE_TOOL_OUTPUT

    msg.unmark_prunable()
    assert not msg.is_prunable
    assert msg.pruning_reason == PruningReason.NOT_PRUNABLE


def test_unified_session_computed_metrics(sample_session: UnifiedSession):
    assert sample_session.total_tokens == 18 + 25 + 1500 + 20 + 120
    # Initially none are marked prunable
    assert sample_session.prunable_tokens == 0
    assert sample_session.noise_ratio == 0.0

    # Mark tool output as prunable
    sample_session.messages[2].mark_prunable(PruningReason.MASSIVE_TOOL_OUTPUT)
    assert sample_session.prunable_tokens == 1500
    assert sample_session.prunable_messages_count == 1
    assert sample_session.noise_ratio > 0.8  # 1500 out of ~1683 is ~89%


def test_unified_session_breakdowns(sample_session: UnifiedSession):
    cats = sample_session.tokens_by_category()
    assert cats[MessageCategory.USER_INSTRUCTION.value] == 18
    assert cats[MessageCategory.TOOL_OUTPUT.value] == 1500

    counts = sample_session.messages_by_category()
    assert counts[MessageCategory.SIDE_QUEST.value] == 2
    assert counts[MessageCategory.ARCHITECTURE.value] == 1
