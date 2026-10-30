"""Unified data models for the Adaptive Agent Memory Engine (AAME).

These models decouple specific agent harness transcript formats (Antigravity,
Claude Code, Cursor, Cline) from downstream token analysis, KV-cache prefix
evaluation, and context handoff generation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, computed_field


class MessageRole(str, Enum):
    """Normalized message roles across different agent frameworks."""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class MessageCategory(str, Enum):
    """Semantic category assigned to conversation steps by heuristic analysis."""
    ARCHITECTURE = "architecture"          # Design patterns, tech decisions, rules
    CODE = "code"                          # Diffs, code blocks, file edits
    TOOL_CALL = "tool_call"                # Agent intent to call a tool
    TOOL_OUTPUT = "tool_output"            # Output returned by terminal/tools
    ERROR = "error"                        # Stack traces, compiler failures
    SIDE_QUEST = "side_quest"              # Pedagogical or exploratory tangent
    USER_INSTRUCTION = "user_instruction"  # Primary user task or directive
    SYSTEM_PROMPT = "system_prompt"        # Builtin instructions or knowledge
    GENERAL = "general"                    # Conversational chit-chat


class PruningReason(str, Enum):
    """Justification explaining why a message is considered prunable."""
    NOT_PRUNABLE = "not_prunable"
    MASSIVE_TOOL_OUTPUT = "massive_tool_output"
    TRANSIENT_ERROR_RESOLVED = "transient_error_resolved"
    REDUNDANT_FILE_READ = "redundant_file_read"
    PEDAGOGICAL_EXPLANATION = "pedagogical_explanation"
    OBSOLETE_TOOL_CHURN = "obsolete_tool_churn"
    MANUAL_PRUNE = "manual_prune"


class UnifiedMessage(BaseModel):
    """A single normalized message/step within an agent conversation."""
    id: str = Field(description="Unique deterministic ID for the message")
    step_index: int = Field(ge=0, description="Chronological 0-indexed position in conversation")
    role: MessageRole = Field(description="Role of the sender")
    category: MessageCategory = Field(default=MessageCategory.GENERAL, description="Semantic classification")
    content: str = Field(default="", description="Textual body or payload")
    token_count: int = Field(default=0, ge=0, description="Calculated token length")
    is_prunable: bool = Field(default=False, description="Whether this message can be safely squashed/pruned")
    pruning_reason: Optional[PruningReason] = Field(default=None, description="Heuristic reason for pruning")
    timestamp: Optional[datetime] = Field(default=None, description="Original event timestamp")
    tool_name: Optional[str] = Field(default=None, description="Tool name if this was a tool call or output")
    tool_args: Optional[dict[str, Any]] = Field(default=None, description="Tool arguments if applicable")
    exit_code: Optional[int] = Field(default=None, description="Command exit code if this was a terminal execution")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Harness-specific raw properties")

    def mark_prunable(self, reason: PruningReason) -> None:
        """Mark this message as recommended for pruning."""
        self.is_prunable = True
        self.pruning_reason = reason

    def unmark_prunable(self) -> None:
        """Protect this message from pruning."""
        self.is_prunable = False
        self.pruning_reason = PruningReason.NOT_PRUNABLE


class CachePrefixMetrics(BaseModel):
    """Analysis of KV-cache prefix stability across turns."""
    total_turns: int = Field(ge=0, default=0)
    stable_prefix_tokens: int = Field(ge=0, default=0, description="Tokens preserved across consecutive turns")
    longest_prefix_tokens: int = Field(ge=0, default=0, description="Maximum continuous shared prefix")
    first_divergence_turn: Optional[int] = Field(default=None, description="First step where prefix invalidation occurred")
    estimated_cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Estimated prefix cache hit percentage")


class NoiseReport(BaseModel):
    """Summary of noise, tool churn, and context degradation in a session."""
    total_messages: int = Field(ge=0, default=0)
    total_tokens: int = Field(ge=0, default=0)
    prunable_messages: int = Field(ge=0, default=0)
    prunable_tokens: int = Field(ge=0, default=0)
    waste_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Percentage of tokens that can be pruned")
    category_token_breakdown: dict[str, int] = Field(default_factory=dict)
    top_waste_messages: list[UnifiedMessage] = Field(default_factory=list)
    actionable_recommendations: list[str] = Field(default_factory=list)


class UnifiedSession(BaseModel):
    """A complete normalized conversation session parsed from an agent harness."""
    session_id: str = Field(description="Unique session identifier or conversation hash")
    harness_name: str = Field(description="Source harness e.g. 'antigravity', 'claude_code', 'cursor'")
    source_file: Optional[str] = Field(default=None, description="Path to original transcript file")
    messages: list[UnifiedMessage] = Field(default_factory=list, description="Ordered list of conversation steps")
    created_at: Optional[datetime] = Field(default=None, description="Session creation time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session-level metadata")

    @computed_field
    def total_tokens(self) -> int:
        """Total tokens across all messages in session."""
        return sum(m.token_count for m in self.messages)

    @computed_field
    def prunable_tokens(self) -> int:
        """Total tokens classified as safely discardable."""
        return sum(m.token_count for m in self.messages if m.is_prunable)

    @computed_field
    def prunable_messages_count(self) -> int:
        """Count of prunable messages."""
        return sum(1 for m in self.messages if m.is_prunable)

    @computed_field
    def noise_ratio(self) -> float:
        """Proportion of prunable tokens over total tokens."""
        total = self.total_tokens
        if total == 0:
            return 0.0
        return round(self.prunable_tokens / total, 4)

    def tokens_by_category(self) -> dict[str, int]:
        """Group token counts by message category."""
        breakdown: dict[str, int] = {}
        for m in self.messages:
            cat = m.category.value
            breakdown[cat] = breakdown.get(cat, 0) + m.token_count
        return breakdown

    def messages_by_category(self) -> dict[str, int]:
        """Group message count by category."""
        counts: dict[str, int] = {}
        for m in self.messages:
            cat = m.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_prunable_messages(self) -> list[UnifiedMessage]:
        """Return all messages marked as prunable."""
        return [m for m in self.messages if m.is_prunable]

    def add_message(self, message: UnifiedMessage) -> None:
        """Add a unified message and ensure step ordering."""
        if not message.step_index:
            message.step_index = len(self.messages)
        self.messages.append(message)
