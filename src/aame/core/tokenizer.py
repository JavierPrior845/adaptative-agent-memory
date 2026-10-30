"""Local, zero-cost token counter and KV-cache prefix comparator using tiktoken.

Provides deterministic token metrics without requiring internet connectivity
or paid third-party API calls.
"""

from __future__ import annotations

import logging
from typing import Optional

from aame.core.models import UnifiedMessage

logger = logging.getLogger(__name__)


class TokenCounter:
    """Thread-safe, local token counter with multi-encoding support and fallback estimation."""

    DEFAULT_ENCODING = "cl100k_base"

    def __init__(self, encoding_name: str = DEFAULT_ENCODING) -> None:
        """Initialize the token counter.
        
        Args:
            encoding_name: Name of the tiktoken encoding (e.g. 'cl100k_base', 'o200k_base').
        """
        self.encoding_name = encoding_name
        self._encoder = None
        self._fallback_mode = False
        self._init_encoder()

    def _init_encoder(self) -> None:
        """Attempt to load tiktoken encoding; switch to heuristic fallback if unavailable."""
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding(self.encoding_name)
            self._fallback_mode = False
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Could not initialize tiktoken encoding '%s': %s. Falling back to heuristic estimator.",
                self.encoding_name,
                exc,
            )
            self._fallback_mode = True

    @property
    def is_fallback(self) -> bool:
        """Whether the counter is operating in heuristic fallback mode."""
        return self._fallback_mode

    def count_tokens(self, text: Optional[str]) -> int:
        """Count the exact (or estimated) number of tokens in a string.
        
        Args:
            text: Input string to tokenize.
            
        Returns:
            Non-negative integer token count.
        """
        if not text:
            return 0

        if not self._fallback_mode and self._encoder is not None:
            try:
                return len(self._encoder.encode(text, disallowed_special=()))
            except Exception as exc:
                logger.debug("tiktoken encoding failed, falling back to heuristic: %s", exc)

        return self._heuristic_estimate(text)

    def count_message(self, message: UnifiedMessage) -> int:
        """Calculate and update token_count on a UnifiedMessage.
        
        Args:
            message: UnifiedMessage to count and mutate in-place.
            
        Returns:
            The calculated token count.
        """
        tokens = self.count_tokens(message.content)
        # If message has tool arguments, also account for the structural payload
        if message.tool_args:
            args_str = str(message.tool_args)
            tokens += self.count_tokens(args_str)
        message.token_count = tokens
        return tokens

    def batch_count(self, texts: list[str]) -> list[int]:
        """Count tokens for a batch of strings.
        
        Args:
            texts: List of strings.
            
        Returns:
            List of token counts in the same order.
        """
        return [self.count_tokens(t) for t in texts]

    def encode(self, text: str) -> list[int]:
        """Encode a string into a list of token IDs.
        
        Args:
            text: Input string.
            
        Returns:
            List of integer token IDs.
        """
        if not text:
            return []
        if not self._fallback_mode and self._encoder is not None:
            return self._encoder.encode(text, disallowed_special=())
        # Fallback fake token IDs based on split
        return list(range(self._heuristic_estimate(text)))

    def common_prefix_tokens(self, text_a: str, text_b: str) -> int:
        """Calculate the length of the identical shared token prefix between two texts.
        
        This metric directly models KV-cache prefix reuse (Prefix Caching).
        If turn B diverges from turn A at token 50, only 50 tokens hit the cache.
        
        Args:
            text_a: First turn text.
            text_b: Second turn text.
            
        Returns:
            Count of identical leading tokens.
        """
        if not text_a or not text_b:
            return 0

        tokens_a = self.encode(text_a)
        tokens_b = self.encode(text_b)

        match_count = 0
        min_len = min(len(tokens_a), len(tokens_b))
        for i in range(min_len):
            if tokens_a[i] == tokens_b[i]:
                match_count += 1
            else:
                break
        return match_count

    @staticmethod
    def _heuristic_estimate(text: str) -> int:
        """Deterministically estimate token count without an external vocabulary.
        
        In English and source code:
        - 1 token is approximately 3.8 to 4.2 characters.
        - Punctuation, symbols and whitespaces create small tokens.
        """
        length = len(text)
        if length == 0:
            return 0
        # Words estimation combined with character length
        words = len(text.split())
        chars = length
        # Standard balanced ratio: max(words, chars / 4)
        return max(1, int(round((chars / 4.0) * 0.7 + words * 0.3)))
