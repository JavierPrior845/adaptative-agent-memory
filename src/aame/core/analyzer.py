"""Context analyzer and heuristic noise detector for agent conversation sessions.

Identifies context degradation, massive tool churn, side-quests, and transient errors,
providing automated pruning suggestions and noise reports without LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from aame.core.models import (
    MessageCategory,
    MessageRole,
    NoiseReport,
    PruningReason,
    UnifiedMessage,
    UnifiedSession,
)
from aame.core.tokenizer import TokenCounter


@dataclass
class AnalyzerThresholds:
    """Configurable thresholds for heuristic classification and pruning."""
    massive_tool_tokens: int = 800          # Tool outputs above this are considered bloated
    extreme_tool_tokens: int = 2500        # Extreme dumps (e.g. whole file dumps, large greps)
    side_quest_min_length: int = 150       # Min length to evaluate for tangential explanations
    max_code_density_for_side_quest: float = 0.05  # Ratio of code characters to disqualify side-quest


class ContextAnalyzer:
    """Heuristic engine that classifies messages and detects conversational noise."""

    # Keywords signaling architectural decisions and permanent project constraints
    ARCHITECTURE_PATTERNS = [
        r"\b(arquitectura|architecture)\b",
        r"\b(decisi[oó]n|decidimos|optamos por)\b",
        r"\b(diseño|design pattern|patr[oó]n)\b",
        r"\b(convenci[oó]n|directriz|guideline|regla|rule)\b",
        r"\b(stack|tecnolog[ií]a|trade-off)\b",
        r"\b(ADR|RFC|roadmap)\b",
    ]

    # Patterns indicating educational / tangential inquiries
    SIDE_QUEST_PATTERNS = [
        r"\bc[oó]mo funciona\b",
        r"\bexpl[ií]came\b",
        r"\bqu[eé] diferencia hay\b",
        r"\bqu[eé] significa\b",
        r"\bqu[eé] es un[a]?\b",
        r"\btell me (how|about|the difference)\b",
        r"\bexplain (to me|how|why)\b",
        r"\bwhat does .+ mean\b",
        r"\bpedag[oó]gic\b",
    ]

    # Error indicators in tool outputs or assistant messages
    ERROR_PATTERNS = [
        r"Traceback \(most recent call last\):",
        r"\b(Error|Exception|Fatal|FAILED|Panic|SyntaxError|TypeError|ValueError):",
        r"The command exited with code [1-9]",
        r"npm ERR!",
        r"cargo error",
        r"fatal:",
    ]

    def __init__(
        self,
        token_counter: Optional[TokenCounter] = None,
        thresholds: Optional[AnalyzerThresholds] = None,
    ) -> None:
        """Initialize ContextAnalyzer.
        
        Args:
            token_counter: TokenCounter instance.
            thresholds: Tuning parameters for noise detection.
        """
        self.counter = token_counter or TokenCounter()
        self.thresholds = thresholds or AnalyzerThresholds()

        self._arch_re = re.compile("|".join(self.ARCHITECTURE_PATTERNS), re.IGNORECASE)
        self._side_re = re.compile("|".join(self.SIDE_QUEST_PATTERNS), re.IGNORECASE)
        self._err_re = re.compile("|".join(self.ERROR_PATTERNS), re.IGNORECASE)

    def analyze_session(self, session: UnifiedSession) -> NoiseReport:
        """Process an entire session: classify categories, calculate tokens, and detect noise.
        
        Mutates messages in place with token counts, categories, and pruning suggestions,
        then returns a comprehensive NoiseReport.
        
        Args:
            session: The UnifiedSession to analyze.
            
        Returns:
            NoiseReport detailing noise distribution and top waste items.
        """
        # Step 1: Ensure all messages have accurate token counts
        for msg in session.messages:
            if msg.token_count <= 0:
                self.counter.count_message(msg)

        # Step 2: Classify semantic categories
        for i, msg in enumerate(session.messages):
            if msg.category == MessageCategory.GENERAL:
                msg.category = self.classify_category(msg)

        # Step 3: Run noise detection and pruning heuristics
        self._apply_pruning_heuristics(session)

        # Step 4: Build noise report
        return self._generate_report(session)

    def classify_category(self, message: UnifiedMessage) -> MessageCategory:
        """Classify a message into its primary semantic category.
        
        Args:
            message: Message to evaluate.
            
        Returns:
            MessageCategory enum.
        """
        content = message.content or ""
        role = message.role

        # Tool calls and outputs
        if role == MessageRole.TOOL:
            if message.exit_code is not None and message.exit_code != 0:
                return MessageCategory.ERROR
            if self._err_re.search(content):
                return MessageCategory.ERROR
            return MessageCategory.TOOL_OUTPUT

        if message.tool_name is not None and role == MessageRole.ASSISTANT and not content.strip():
            return MessageCategory.TOOL_CALL

        # System messages
        if role == MessageRole.SYSTEM:
            return MessageCategory.SYSTEM_PROMPT

        # User messages
        if role == MessageRole.USER:
            if "<USER_REQUEST>" in content:
                # Check if user is asking a purely educational side question
                clean_req = self._extract_user_request(content)
                if self._side_re.search(clean_req):
                    return MessageCategory.SIDE_QUEST
                return MessageCategory.USER_INSTRUCTION
            if self._side_re.search(content):
                return MessageCategory.SIDE_QUEST
            return MessageCategory.USER_INSTRUCTION

        # Assistant messages
        if self._arch_re.search(content):
            return MessageCategory.ARCHITECTURE

        if self._has_significant_code(content):
            return MessageCategory.CODE

        if self._side_re.search(content) and self._is_low_code_density(content):
            return MessageCategory.SIDE_QUEST

        if self._err_re.search(content):
            return MessageCategory.ERROR

        return MessageCategory.GENERAL

    def _apply_pruning_heuristics(self, session: UnifiedSession) -> None:
        """Evaluate messages for safe context pruning and mark them."""
        messages = session.messages

        # Track resolved errors: if an error occurs and a later tool call succeeds, it's transient
        last_success_index = -1
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg.role == MessageRole.TOOL and msg.exit_code == 0:
                last_success_index = i
                break

        for i, msg in enumerate(messages):
            # ARCHITECTURE and USER_INSTRUCTION are protected by default
            if msg.category in (MessageCategory.ARCHITECTURE, MessageCategory.USER_INSTRUCTION):
                msg.unmark_prunable()
                continue

            # Case 1: Massive or Extreme Tool Outputs (view_file of entire files, massive grep dumps)
            if msg.category == MessageCategory.TOOL_OUTPUT:
                if msg.token_count >= self.thresholds.massive_tool_tokens:
                    msg.mark_prunable(PruningReason.MASSIVE_TOOL_OUTPUT)
                    continue

                # Repetitive directory listings or file viewings
                if msg.tool_name in ("list_dir", "view_file", "read_url_content") and msg.token_count > 300:
                    msg.mark_prunable(PruningReason.OBSOLETE_TOOL_CHURN)
                    continue

            # Case 2: Transient Errors that were subsequently resolved
            if msg.category == MessageCategory.ERROR and i < last_success_index:
                msg.mark_prunable(PruningReason.TRANSIENT_ERROR_RESOLVED)
                continue

            # Case 3: Pure Side-Quests (pedagogical explanations with no code impact)
            if msg.category == MessageCategory.SIDE_QUEST:
                msg.mark_prunable(PruningReason.PEDAGOGICAL_EXPLANATION)
                continue

    def _generate_report(self, session: UnifiedSession) -> NoiseReport:
        """Compile a NoiseReport from an analyzed session."""
        total_tokens = session.total_tokens
        prunable_tokens = session.prunable_tokens
        total_messages = len(session.messages)
        prunable_messages = session.prunable_messages_count

        waste_ratio = round(prunable_tokens / total_tokens, 4) if total_tokens > 0 else 0.0

        # Top waste messages sorted by token count descending
        prunable_list = sorted(
            session.get_prunable_messages(),
            key=lambda m: m.token_count,
            reverse=True,
        )
        top_waste = prunable_list[:5]

        # Actionable recommendations
        recommendations = []
        if waste_ratio > 0.5:
            recommendations.append(
                f"Critical Context Bloat: {waste_ratio * 100:.1f}% of session tokens ({prunable_tokens:,} tokens) "
                "are discardable tool churn or side-quests. A squash/handoff is strongly advised."
            )
        elif waste_ratio > 0.25:
            recommendations.append(
                f"Moderate Noise: {waste_ratio * 100:.1f}% of context ({prunable_tokens:,} tokens) "
                "can be pruned to optimize attention and reduce prefix cache cost."
            )

        massive_tools = [m for m in prunable_list if m.pruning_reason == PruningReason.MASSIVE_TOOL_OUTPUT]
        if massive_tools:
            tool_tokens = sum(m.token_count for m in massive_tools)
            recommendations.append(
                f"{len(massive_tools)} massive tool outputs consume {tool_tokens:,} tokens. "
                "Squashing raw tool logs will prevent 'Lost in the Middle' degradation."
            )

        side_quests = [m for m in prunable_list if m.pruning_reason == PruningReason.PEDAGOGICAL_EXPLANATION]
        if side_quests:
            recommendations.append(
                f"{len(side_quests)} pedagogical side-quests detected. Safe to omit from project memory."
            )

        return NoiseReport(
            total_messages=total_messages,
            total_tokens=total_tokens,
            prunable_messages=prunable_messages,
            prunable_tokens=prunable_tokens,
            waste_ratio=waste_ratio,
            category_token_breakdown=session.tokens_by_category(),
            top_waste_messages=top_waste,
            actionable_recommendations=recommendations,
        )

    @staticmethod
    def _extract_user_request(content: str) -> str:
        """Extract only the core user instruction inside <USER_REQUEST> tags."""
        match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content

    @staticmethod
    def _has_significant_code(content: str) -> bool:
        """Check if content has markdown code fences or syntax definitions."""
        if "```" in content:
            return True
        code_keywords = [r"\bdef\s+\w+\(", r"\bclass\s+\w+", r"\bfunction\s+\w+\(", r"\bimport\s+\w+"]
        for kw in code_keywords:
            if re.search(kw, content):
                return True
        return False

    def _is_low_code_density(self, content: str) -> bool:
        """Check if the text contains almost no code characters."""
        code_chars = sum(content.count(c) for c in "{}[]();=<>/*")
        total = max(1, len(content))
        return (code_chars / total) <= self.thresholds.max_code_density_for_side_quest
