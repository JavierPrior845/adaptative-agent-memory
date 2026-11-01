"""Interactive list widget for agent conversation sessions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from aame.adapters.antigravity import AntigravityAdapter


class SessionItem(ListItem):
    """An individual session item inside the session list."""

    def __init__(self, session_path: Path, session_id: str, mtime: float) -> None:
        super().__init__()
        self.session_path = session_path
        self.session_id = session_id
        self.mtime = mtime

    def compose(self):
        dt_str = datetime.fromtimestamp(self.mtime).strftime("%d/%m %H:%M")
        short_id = self.session_id[:12] + "..." if len(self.session_id) > 12 else self.session_id

        text = Text()
        text.append("◆ ", style="#58a6ff")
        text.append(f"{short_id}\n", style="bold #f0f6fc")
        text.append(f"  {dt_str}", style="#8b949e")
        yield Static(text)


class SessionListView(ListView):
    """List of sessions discovered by local adapters."""

    class SessionSelected(Message):
        """Emitted when user selects a session."""
        def __init__(self, session_path: Path) -> None:
            super().__init__()
            self.session_path = session_path

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.adapter = AntigravityAdapter()

    def on_mount(self) -> None:
        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        """Find local sessions and populate list."""
        self.clear()
        sessions = self.adapter.discover_sessions()
        for p in sessions[:25]:
            mtime = p.stat().st_mtime
            conv_id = self.adapter._extract_session_id(p)
            self.append(SessionItem(p, conv_id, mtime))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, SessionItem):
            self.post_message(self.SessionSelected(event.item.session_path))
