"""Interactive messages table allowing turn inspection and pruning toggling."""

from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from aame.core.models import MessageCategory, UnifiedMessage, UnifiedSession


class MessagesTable(DataTable):
    """DataTable listing conversation turns with category badges and pruning state."""

    class MessageHighlighted(Message):
        """Emitted when user moves cursor over a message."""
        def __init__(self, message: UnifiedMessage) -> None:
            super().__init__()
            self.message = message

    class PruningToggled(Message):
        """Emitted when user presses space/toggle to prune/unprune a message."""
        def __init__(self, message: UnifiedMessage) -> None:
            super().__init__()
            self.message = message

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self._messages_by_row: dict[int, UnifiedMessage] = {}

    def on_mount(self) -> None:
        self.add_column("St", width=4)
        self.add_column("Keep", width=5)
        self.add_column("Tokens", width=7)
        self.add_column("Category", width=12)
        self.add_column("Summary / Tool", width=25)

    def load_session(self, session: UnifiedSession) -> None:
        """Populate table with messages from UnifiedSession."""
        self.clear()
        self._messages_by_row.clear()

        for idx, m in enumerate(session.messages):
            self._messages_by_row[idx] = m

            # Keep icon: [✔] or [x]
            keep_str = " ✔ " if not m.is_prunable else " ✖ "
            keep_style = "#3fb950" if not m.is_prunable else "#d29922"

            # Category badge styling
            cat_color = {
                MessageCategory.ARCHITECTURE: "#58a6ff",
                MessageCategory.USER_INSTRUCTION: "#58a6ff",
                MessageCategory.CODE: "#79c0ff",
                MessageCategory.TOOL_OUTPUT: "#bc8cff",
                MessageCategory.TOOL_CALL: "#d2a8ff",
                MessageCategory.ERROR: "#f85149",
                MessageCategory.SIDE_QUEST: "#d29922",
            }.get(m.category, "#8b949e")

            # Summary snippet
            summary = m.tool_name if m.tool_name else (m.content[:30].replace("\n", " ") if m.content else "")

            self.add_row(
                Text(str(m.step_index), style="#8b949e"),
                Text(keep_str, style=f"bold {keep_style}"),
                Text(f"{m.token_count:>5}", style="bold #f0f6fc"),
                Text(m.category.value[:11], style=f"bold {cat_color}"),
                Text(summary[:24], style="#c9d1d9"),
                key=str(idx),
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row in self._messages_by_row:
            msg = self._messages_by_row[event.cursor_row]
            self.post_message(self.MessageHighlighted(msg))

    def toggle_current_row_pruning(self) -> None:
        """Toggle prunable flag on currently highlighted message."""
        row_idx = self.cursor_row
        if row_idx in self._messages_by_row:
            msg = self._messages_by_row[row_idx]
            msg.is_prunable = not msg.is_prunable
            # Re-render keep status cell
            keep_str = " ✔ " if not msg.is_prunable else " ✖ "
            keep_style = "#3fb950" if not msg.is_prunable else "#d29922"
            self.update_cell_at((row_idx, 1), Text(keep_str, style=f"bold {keep_style}"))
            self.post_message(self.PruningToggled(msg))
