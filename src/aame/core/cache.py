"""KV-Cache and Prefix Caching analyzer for agent conversations.

Evaluates prefix continuity, cache hit/miss economics, and context bloat across turns.
"""

from __future__ import annotations

from typing import Optional

from aame.core.models import CachePrefixMetrics, UnifiedSession
from aame.core.tokenizer import TokenCounter


class KVCacheAnalyzer:
    """Simulates and measures prefix caching behavior (Anthropic/OpenAI/vLLM style)."""

    def __init__(self, token_counter: Optional[TokenCounter] = None) -> None:
        """Initialize the KV cache analyzer.
        
        Args:
            token_counter: TokenCounter instance. If None, creates a default one.
        """
        self.counter = token_counter or TokenCounter()

    def analyze_session(self, session: UnifiedSession) -> CachePrefixMetrics:
        """Analyze prefix continuity across messages in a session.
        
        Evaluates how strictly append-only the conversation stream is and
        calculates estimated cache reuse vs full context recomputation.
        
        Args:
            session: UnifiedSession containing chronologically ordered messages.
            
        Returns:
            CachePrefixMetrics detailing prefix reuse rates.
        """
        messages = session.messages
        if not messages:
            return CachePrefixMetrics()

        total_turns = len(messages)
        if total_turns == 1:
            tokens = messages[0].token_count or self.counter.count_message(messages[0])
            return CachePrefixMetrics(
                total_turns=1,
                stable_prefix_tokens=tokens,
                longest_prefix_tokens=tokens,
                first_divergence_turn=None,
                estimated_cache_hit_rate=0.0,
            )

        # Build turn-by-turn cumulative text
        turn_cumulative_texts: list[str] = []
        cumulative_buffer = ""
        for msg in messages:
            prefix_chunk = f"{msg.role.value}: {msg.content}\n"
            cumulative_buffer += prefix_chunk
            turn_cumulative_texts.append(cumulative_buffer)

        # Compare consecutive turns for prefix preservation
        total_shared_tokens = 0
        total_possible_prefix_tokens = 0
        longest_prefix = 0
        first_divergence: Optional[int] = None

        for i in range(1, len(turn_cumulative_texts)):
            prev_turn = turn_cumulative_texts[i - 1]
            curr_turn = turn_cumulative_texts[i]

            prev_tokens = self.counter.count_tokens(prev_turn)
            shared_prefix = self.counter.common_prefix_tokens(prev_turn, curr_turn)

            total_possible_prefix_tokens += prev_tokens
            total_shared_tokens += shared_prefix
            if shared_prefix > longest_prefix:
                longest_prefix = shared_prefix

            # Divergence occurs if the current turn does not completely include the previous prefix
            if shared_prefix < prev_tokens and first_divergence is None:
                first_divergence = i

        hit_rate = 0.0
        if total_possible_prefix_tokens > 0:
            hit_rate = round(total_shared_tokens / total_possible_prefix_tokens, 4)

        stable_prefix = total_shared_tokens // (total_turns - 1) if total_turns > 1 else 0

        return CachePrefixMetrics(
            total_turns=total_turns,
            stable_prefix_tokens=stable_prefix,
            longest_prefix_tokens=longest_prefix,
            first_divergence_turn=first_divergence,
            estimated_cache_hit_rate=hit_rate,
        )
