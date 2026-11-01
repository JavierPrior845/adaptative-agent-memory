"""Detail pane for inspecting selected message content, tool arguments, and metadata."""

from __future__ import annotations

from rich.syntax import Syntax
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static

from aame.core.models import UnifiedMessage


class MessageDetailPane(VerticalScroll):
    """Detailed view of the highlighted conversation step."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.static_widget = Static(id="detail-static")

    def compose(self):
        yield self.static_widget

    def show_message(self, message: UnifiedMessage) -> None:
        """Render detailed view of message."""
        text = Text()

        # Step and Role header
        text.append(f"Step #{message.step_index}", style="bold #58a6ff")
        text.append(f"  [{message.role.value.upper()}]", style="bold #f0f6fc")
        text.append(f"  |  Category: {message.category.value}\n", style="#8b949e")

        # Tokens & Pruning state
        status_text = "Discardable (Prunable)" if message.is_prunable else "Active (Clean Core)"
        status_color = "#d29922" if message.is_prunable else "#3fb950"
        text.append("Status: ", style="bold")
        text.append(status_text, style=f"bold {status_color}")
        text.append(f"  |  Tokens: {message.token_count:,}\n", style="bold #c9d1d9")

        if message.pruning_reason:
            text.append(f"Pruning Reason: {message.pruning_reason.value}\n", style="#d29922")

        if message.tool_name:
            text.append(f"Tool: {message.tool_name}\n", style="bold #bc8cff")

        if message.exit_code is not None:
            code_color = "#3fb950" if message.exit_code == 0 else "#f85149"
            text.append(f"Exit Code: {message.exit_code}\n", style=f"bold {code_color}")

        text.append("\n" + "─" * 40 + "\n", style="#30363d")

        # Content preview (up to 3000 chars for responsive rendering)
        content = message.content or ""
        if len(content) > 3000:
            preview = content[:3000] + "\n... [Output truncated for UI performance]"
        else:
            preview = content

        text.append(preview, style="#c9d1d9")
        self.static_widget.update(text)
