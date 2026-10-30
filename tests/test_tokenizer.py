"""Unit tests for TokenCounter and prefix matching."""

from aame.core.models import MessageCategory, MessageRole, UnifiedMessage
from aame.core.tokenizer import TokenCounter


def test_token_counter_basic(token_counter: TokenCounter):
    text = "Hello world from the Adaptive Agent Memory Engine"
    count = token_counter.count_tokens(text)
    assert count > 0
    assert isinstance(count, int)


def test_token_counter_empty_and_none(token_counter: TokenCounter):
    assert token_counter.count_tokens("") == 0
    assert token_counter.count_tokens(None) == 0


def test_token_counter_message_mutation(token_counter: TokenCounter):
    msg = UnifiedMessage(
        id="t-1",
        step_index=0,
        role=MessageRole.USER,
        category=MessageCategory.USER_INSTRUCTION,
        content="Testing token calculation in message payload",
        token_count=0,
    )
    tokens = token_counter.count_message(msg)
    assert tokens > 0
    assert msg.token_count == tokens


def test_token_counter_batch(token_counter: TokenCounter):
    texts = ["Alpha", "Beta gamma delta", "One more string to test"]
    counts = token_counter.batch_count(texts)
    assert len(counts) == 3
    assert all(c > 0 for c in counts)


def test_common_prefix_tokens(token_counter: TokenCounter):
    # Same prefix, different ending
    text_a = "The quick brown fox jumps over the lazy dog"
    text_b = "The quick brown fox jumps over the sleeping cat"
    shared = token_counter.common_prefix_tokens(text_a, text_b)
    assert shared >= 6  # "The quick brown fox jumps over the" should share at least 6-7 tokens


def test_common_prefix_empty(token_counter: TokenCounter):
    assert token_counter.common_prefix_tokens("", "Hello") == 0
    assert token_counter.common_prefix_tokens("Hello", "") == 0


def test_heuristic_fallback():
    # Force fallback mode to test deterministic estimation
    counter = TokenCounter()
    counter._fallback_mode = True
    estimate = counter.count_tokens("This is a heuristic fallback test for zero-dependency execution.")
    assert estimate > 0
    assert isinstance(estimate, int)
