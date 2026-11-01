"""Unit tests for the AAME TUI Cockpit App."""

import pytest
from pathlib import Path
from aame.tui.app import AAMECockpitApp
from aame.tui.widgets.token_meter import render_token_meter


def test_render_token_meter():
    bar = render_token_meter(used=64_000, limit=128_000, width=20)
    assert "64,000 / 128,000" in bar
    assert "50.0%" in bar
    assert "█" in bar


@pytest.mark.asyncio
async def test_tui_app_mount(synthetic_transcript_path: Path):
    app = AAMECockpitApp(initial_session_path=synthetic_transcript_path)
    async with app.run_test() as pilot:
        # Check that main layout elements mounted successfully
        assert app.query_one("#main-container") is not None
        assert app.query_one("#token-meter") is not None
        assert app.query_one("#messages-table") is not None
        assert app.query_one("#detail-pane") is not None

        # Check session is loaded
        assert app.current_session is not None
        assert app.current_session.session_id == "conv-uuid-1234"

        # Test toggle prune action
        app.action_toggle_prune()
        # Test squash handoff action
        app.action_squash_handoff()
