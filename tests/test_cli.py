"""Unit tests for the AAME Typer CLI."""

from typer.testing import CliRunner
from aame.cli.app import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Adaptive Agent Memory Engine (AAME)" in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "squash" in result.stdout
    assert "sessions" in result.stdout


def test_cli_sessions():
    result = runner.invoke(app, ["sessions", "--limit", "3"])
    assert result.exit_code == 0
    assert "Discovered Agent Sessions" in result.stdout


def test_cli_inspect_synthetic(synthetic_transcript_path):
    result = runner.invoke(app, ["inspect", str(synthetic_transcript_path)])
    assert result.exit_code == 0
    assert "Token & Context Audit" in result.stdout
    assert "Total Steps / Messages" in result.stdout


def test_cli_squash_synthetic(synthetic_transcript_path, tmp_path):
    out_file = tmp_path / "HANDOFF_TEST.md"
    result = runner.invoke(app, ["squash", str(synthetic_transcript_path), "--output", str(out_file), "--print"])
    assert result.exit_code == 0
    assert "Handoff successfully created!" in result.stdout
    assert out_file.is_file()
