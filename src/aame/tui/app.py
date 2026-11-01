"""Main Interactive Cockpit Application for AAME built with Textual."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from aame.adapters.antigravity import AntigravityAdapter
from aame.core.analyzer import ContextAnalyzer
from aame.core.cache import KVCacheAnalyzer
from aame.core.handoff import HandoffGenerator
from aame.core.models import UnifiedSession
from aame.core.tokenizer import TokenCounter
from aame.tui.widgets.detail_pane import MessageDetailPane
from aame.tui.widgets.message_table import MessagesTable
from aame.tui.widgets.session_list import SessionListView
from aame.tui.widgets.token_meter import TokenMeterWidget


class AAMECockpitApp(App):
    """Interactive Context Management & Memory Engine Cockpit."""

    CSS_PATH = "styles.tcss"
    TITLE = "AAME Context Cockpit"
    SUB_TITLE = "Adaptive Agent Memory Engine"

    BINDINGS = [
        ("q", "quit", "Salir"),
        ("space", "toggle_prune", "Alternar Podado"),
        ("s", "squash_handoff", "Generar Handoff"),
        ("p", "prune_all_noise", "Podar Todo Ruido"),
        ("r", "refresh_session", "Recargar Sesión"),
        ("tab", "focus_next", "Cambiar Foco"),
    ]

    def __init__(self, initial_session_path: Optional[Path] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.initial_session_path = initial_session_path
        self.current_session: Optional[UnifiedSession] = None
        self.adapter = AntigravityAdapter()
        self.counter = TokenCounter()
        self.analyzer = ContextAnalyzer(token_counter=self.counter)
        self.cache_analyzer = KVCacheAnalyzer(token_counter=self.counter)
        self.handoff_generator = HandoffGenerator()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            # Sidebar: Discovered agent sessions
            with Vertical(id="sidebar"):
                yield Static("◆ SESIONES DESCUBIERTAS", classes="pane-title")
                yield SessionListView(id="session-list")

            # Workspace: Cockpit meters, turns table, and message details
            with Vertical(id="workspace"):
                # Metrics Banner
                with Container(id="metrics-panel"):
                    yield TokenMeterWidget(id="token-meter")

                # Split turns and details
                with Horizontal(id="split-workspace"):
                    with Vertical(id="messages-container"):
                        yield Static("LISTA DE TURNOS (Espacio: Podar)", classes="pane-title-dim")
                        yield MessagesTable(id="messages-table")

                    with Vertical(id="detail-container"):
                        yield Static("DETALLE DE TURNO SELECCIONADO", classes="pane-title-dim")
                        yield MessageDetailPane(id="detail-pane")

        yield Footer()

    def on_mount(self) -> None:
        """Load initial session when UI starts."""
        target = self.initial_session_path
        if not target:
            sessions = self.adapter.discover_sessions()
            if sessions:
                target = sessions[0]

        if target:
            self._load_session(target)

    def on_session_list_view_session_selected(self, event: SessionListView.SessionSelected) -> None:
        """Handle session click from sidebar."""
        self._load_session(event.session_path)

    def _load_session(self, path: Path) -> None:
        """Parse and display target session."""
        try:
            self.current_session = self.adapter.parse(path)
            report = self.analyzer.analyze_session(self.current_session)
            cache_metrics = self.cache_analyzer.analyze_session(self.current_session)

            # Update widgets
            meter = self.query_one(TokenMeterWidget)
            meter.update_metrics(report, cache_metrics)

            table = self.query_one(MessagesTable)
            table.load_session(self.current_session)

            self.notify(
                f"Sesión cargada: {self.current_session.session_id[:8]}... ({report.total_tokens:,} tokens)",
                title="AAME Cockpit",
            )
        except Exception as exc:
            self.notify(f"Error cargando sesión: {exc}", severity="error")

    def on_messages_table_message_highlighted(self, event: MessagesTable.MessageHighlighted) -> None:
        """Update detail pane when user moves row cursor."""
        detail_pane = self.query_one(MessageDetailPane)
        detail_pane.show_message(event.message)

    def on_messages_table_pruning_toggled(self, event: MessagesTable.PruningToggled) -> None:
        """Recalculate metrics when individual turn is toggled."""
        if self.current_session:
            report = self.analyzer._generate_report(self.current_session)
            cache_metrics = self.cache_analyzer.analyze_session(self.current_session)
            self.query_one(TokenMeterWidget).update_metrics(report, cache_metrics)

    def action_toggle_prune(self) -> None:
        """Toggle keep/prune on the selected row via Spacebar."""
        table = self.query_one(MessagesTable)
        table.toggle_current_row_pruning()

    def action_prune_all_noise(self) -> None:
        """Automatically mark all recommended noise for pruning."""
        if not self.current_session:
            return
        self.analyzer._apply_pruning_heuristics(self.current_session)
        table = self.query_one(MessagesTable)
        table.load_session(self.current_session)
        report = self.analyzer._generate_report(self.current_session)
        cache_metrics = self.cache_analyzer.analyze_session(self.current_session)
        self.query_one(TokenMeterWidget).update_metrics(report, cache_metrics)
        self.notify("Ruido podado automáticamente según heurísticas.", title="Podado completado")

    def action_squash_handoff(self) -> None:
        """Generate HANDOFF.md checkpoint from current session."""
        if not self.current_session:
            self.notify("No hay ninguna sesión activa para realizar squash.", severity="warning")
            return

        state, path, _ = self.handoff_generator.generate_and_save(self.current_session)
        self.notify(
            f"Checkpoint creado con éxito en {path.name} ({len(state.key_decisions)} decisiones)",
            title="✔ Handoff Generado",
        )

    def action_refresh_session(self) -> None:
        """Reload current session from disk."""
        if self.current_session and self.current_session.source_file:
            self._load_session(Path(self.current_session.source_file))


def launch_cockpit(session_path: Optional[Path] = None) -> None:
    """Entry point to launch the TUI Cockpit."""
    app = AAMECockpitApp(initial_session_path=session_path)
    app.run()
