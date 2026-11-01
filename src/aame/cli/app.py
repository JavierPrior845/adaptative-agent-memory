"""CLI Application for AAME (Adaptive Agent Memory Engine).

Provides headless terminal commands for context auditing, token analytics,
and checkpoint handoff generation (squash).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aame import __version__
from aame.adapters.antigravity import AntigravityAdapter
from aame.core.analyzer import ContextAnalyzer
from aame.core.cache import KVCacheAnalyzer
from aame.core.cache_store import SessionCache
from aame.core.handoff import HandoffGenerator
from aame.core.tokenizer import TokenCounter

app = typer.Typer(
    name="aame",
    help="Adaptive Agent Memory Engine: Context Auditing, Token Analytics and Handoff Generator.",
    no_args_is_help=True,
)
console = Console()


def _resolve_session_path(session_arg: Optional[str]) -> Path:
    """Helper to resolve a session ID, folder or transcript file path."""
    adapter = AntigravityAdapter()

    if session_arg:
        p = Path(session_arg)
        if p.is_file():
            return p
        if p.is_dir():
            candidate = p / ".system_generated" / "logs" / "transcript.jsonl"
            if candidate.is_file():
                return candidate
            return p

        # Check if session_arg matches a session ID in brain
        all_sessions = adapter.discover_sessions()
        for s in all_sessions:
            if session_arg in str(s):
                return s
        console.print(f"[bold red]Error:[/bold red] Could not find session '{session_arg}'.")
        raise typer.Exit(code=1)

    # Auto-discover latest session
    all_sessions = adapter.discover_sessions()
    if not all_sessions:
        console.print("[bold red]Error:[/bold red] No local Antigravity sessions found.")
        raise typer.Exit(code=1)

    return all_sessions[0]


@app.command("version")
def version_command() -> None:
    """Display AAME version."""
    console.print(f"[bold green]Adaptive Agent Memory Engine (AAME)[/bold green] v{__version__}")


@app.command("sessions")
def list_sessions(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum number of sessions to list."),
) -> None:
    """List available agent sessions discovered on the system."""
    adapter = AntigravityAdapter()
    sessions = adapter.discover_sessions()

    if not sessions:
        console.print("[yellow]No active agent sessions found in standard locations.[/yellow]")
        return

    table = Table(title=f"Discovered Agent Sessions ({len(sessions)} total)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Last Modified", style="magenta")
    table.add_column("Path", style="dim")

    for idx, s in enumerate(sessions[:limit], start=1):
        mtime = s.stat().st_mtime
        from datetime import datetime
        dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        # Extract UUID
        conv_id = adapter._extract_session_id(s)
        table.add_row(str(idx), conv_id, dt_str, str(s))

    console.print(table)
    if len(sessions) > limit:
        console.print(f"[dim]... and {len(sessions) - limit} more sessions.[/dim]")


@app.command("inspect")
def inspect_command(
    session: Optional[str] = typer.Argument(
        None,
        help="Session ID, path to transcript.jsonl, or omit to inspect the latest session.",
    ),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show breakdown of individual steps."),
) -> None:
    """Audit a session's token consumption, KV-Cache continuity, and noise ratio."""
    transcript_path = _resolve_session_path(session)
    adapter = AntigravityAdapter()
    counter = TokenCounter()
    analyzer = ContextAnalyzer(token_counter=counter)
    cache_analyzer = KVCacheAnalyzer(token_counter=counter)
    cache_store = SessionCache()

    console.print(f"[bold blue]Auditing Session:[/bold blue] {transcript_path}")

    # Parse and analyze
    parsed_session = adapter.parse(transcript_path)
    report = analyzer.analyze_session(parsed_session)
    cache_metrics = cache_analyzer.analyze_session(parsed_session)

    # Save to session cache store
    cache_store.save_session(parsed_session, transcript_mtime=transcript_path.stat().st_mtime)

    # Metrics Summary Table
    table = Table(title=f"Token & Context Audit (Session: {parsed_session.session_id})")
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")

    table.add_row("Total Steps / Messages", str(report.total_messages))
    table.add_row("Total Context Tokens", f"{report.total_tokens:,}")
    table.add_row("Prunable / Waste Tokens", f"{report.prunable_tokens:,} ({report.waste_ratio * 100:.1f}%)")
    table.add_row("Clean Core Tokens", f"{report.total_tokens - report.prunable_tokens:,}")
    table.add_row("KV-Cache Hit Rate (Estimated)", f"{cache_metrics.estimated_cache_hit_rate * 100:.1f}%")
    table.add_row("Longest Stable Prefix", f"{cache_metrics.longest_prefix_tokens:,} tokens")

    console.print(table)

    # Breakdown by category
    cat_table = Table(title="Token Distribution by Semantic Category")
    cat_table.add_column("Category", style="green")
    cat_table.add_column("Tokens", justify="right")
    cat_table.add_column("Percentage", justify="right")

    for cat, tokens in sorted(report.category_token_breakdown.items(), key=lambda x: x[1], reverse=True):
        pct = (tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
        cat_table.add_row(cat, f"{tokens:,}", f"{pct:.1f}%")

    console.print(cat_table)

    # Top waste culprits
    if report.top_waste_messages:
        waste_table = Table(title="Top Waste Culprits Recommended for Squash")
        waste_table.add_column("Step", style="dim", width=6)
        waste_table.add_column("Tokens", justify="right", style="red")
        waste_table.add_column("Category / Reason", style="yellow")
        waste_table.add_column("Preview", style="white")

        for m in report.top_waste_messages:
            reason = m.pruning_reason.value if m.pruning_reason else "general_noise"
            preview = m.content[:60].replace("\n", " ") if m.content else ""
            waste_table.add_row(f"#{m.step_index}", f"{m.token_count:,}", f"{m.category.value} ({reason})", preview)

        console.print(waste_table)

    # Recommendations
    if report.actionable_recommendations:
        rec_panel = "\n".join(f"[bold green]•[/bold green] {r}" for r in report.actionable_recommendations)
        console.print(Panel(rec_panel, title="Actionable Optimization Advice", border_style="green"))


@app.command("squash")
def squash_command(
    session: Optional[str] = typer.Argument(
        None,
        help="Session ID, path to transcript.jsonl, or omit to squash the latest session.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output file path for HANDOFF.md (default: ./HANDOFF.md)",
    ),
    print_markdown: bool = typer.Option(
        False,
        "--print",
        "-p",
        help="Print the generated handoff markdown to stdout.",
    ),
) -> None:
    """Generate a clean context handoff (Save Game) to start a new chat without amnesia."""
    transcript_path = _resolve_session_path(session)
    adapter = AntigravityAdapter()
    analyzer = ContextAnalyzer()
    generator = HandoffGenerator()

    console.print(f"[bold cyan]Squashing context from:[/bold cyan] {transcript_path}")

    parsed_session = adapter.parse(transcript_path)
    analyzer.analyze_session(parsed_session)

    # Generate handoff
    state, target_path, content = generator.generate_and_save(parsed_session, output_path=output)

    console.print(f"[bold green]✔ Handoff successfully created![/bold green] Saved to: [bold]{target_path}[/bold]")
    console.print(f"  • Primary Goal: [italic]{state.primary_goal}[/italic]")
    console.print(f"  • Technical Decisions Fixed: {len(state.key_decisions)}")
    console.print(f"  • Discarded Paths / Errors: {len(state.discarded_approaches)}")
    console.print(f"  • Active Files tracked: {len(state.active_files)}")
    console.print(f"  • Next Steps extracted: {len(state.next_steps)}")

    if print_markdown:
        console.print("\n" + "=" * 60)
        console.print(content)
        console.print("=" * 60)


@app.command("cockpit")
def cockpit_command(
    session: Optional[str] = typer.Argument(
        None,
        help="Session ID, path to transcript.jsonl, or omit to launch with latest session.",
    ),
) -> None:
    """Launch the interactive Terminal Cockpit (Textual TUI)."""
    from aame.tui.app import launch_cockpit

    target_path = None
    if session:
        target_path = _resolve_session_path(session)

    launch_cockpit(session_path=target_path)


def main() -> None:
    """Main CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
