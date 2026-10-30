"""Unit tests for ContextAnalyzer and heuristic noise detection."""

from aame.core.analyzer import ContextAnalyzer
from aame.core.models import (
    MessageCategory,
    MessageRole,
    PruningReason,
    UnifiedMessage,
    UnifiedSession,
)


def test_classify_architecture():
    analyzer = ContextAnalyzer()
    msg = UnifiedMessage(
        id="m-1",
        step_index=0,
        role=MessageRole.ASSISTANT,
        content="Hemos tomado la decisión de arquitectura de persistir la memoria en un archivo JSON en disco.",
    )
    cat = analyzer.classify_category(msg)
    assert cat == MessageCategory.ARCHITECTURE


def test_classify_side_quest():
    analyzer = ContextAnalyzer()
    msg = UnifiedMessage(
        id="m-2",
        step_index=0,
        role=MessageRole.USER,
        content="Oye, explícame cómo funciona la memoria virtual en sistemas operativos.",
    )
    cat = analyzer.classify_category(msg)
    assert cat == MessageCategory.SIDE_QUEST


def test_classify_error_tool():
    analyzer = ContextAnalyzer()
    msg = UnifiedMessage(
        id="m-3",
        step_index=0,
        role=MessageRole.TOOL,
        exit_code=1,
        content="SyntaxError: invalid syntax on line 42",
    )
    cat = analyzer.classify_category(msg)
    assert cat == MessageCategory.ERROR


def test_detect_massive_tool_output(sample_session: UnifiedSession):
    analyzer = ContextAnalyzer()
    report = analyzer.analyze_session(sample_session)

    # Message 2 in sample_session has 1500 tokens of dumped code from view_file
    msg_2 = sample_session.messages[2]
    assert msg_2.is_prunable
    assert msg_2.pruning_reason == PruningReason.MASSIVE_TOOL_OUTPUT

    # Architecture message should NEVER be prunable
    msg_arch = sample_session.messages[1]
    assert not msg_arch.is_prunable

    # Noise report should reflect high waste
    assert report.waste_ratio > 0.5
    assert len(report.top_waste_messages) >= 1
    assert report.top_waste_messages[0].id == "s1-msg-2"
    assert len(report.actionable_recommendations) > 0


def test_transient_error_pruning():
    analyzer = ContextAnalyzer()
    session = UnifiedSession(
        session_id="error-session",
        harness_name="antigravity",
        messages=[
            UnifiedMessage(
                id="e1",
                step_index=0,
                role=MessageRole.TOOL,
                category=MessageCategory.ERROR,
                exit_code=1,
                content="Traceback (most recent call last):\nTypeError: cannot unpack non-iterable NoneType object",
                token_count=100,
            ),
            UnifiedMessage(
                id="e2",
                step_index=1,
                role=MessageRole.TOOL,
                category=MessageCategory.TOOL_OUTPUT,
                exit_code=0,
                content="Tests passed successfully: 12 passed.",
                token_count=50,
            ),
        ],
    )
    analyzer.analyze_session(session)
    # The first error was resolved by step 1, so it should be marked prunable
    assert session.messages[0].is_prunable
    assert session.messages[0].pruning_reason == PruningReason.TRANSIENT_ERROR_RESOLVED
