"""AAME Phase 1 Demonstration & Audit CLI.

Runs local token analysis, KV-cache prefix stability checks, and noise detection
on real Antigravity sessions or synthetic test logs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to sys.path for direct execution
pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from aame.adapters.antigravity import AntigravityAdapter
from aame.core.analyzer import ContextAnalyzer
from aame.core.cache import KVCacheAnalyzer
from aame.core.tokenizer import TokenCounter


def format_bar(ratio: float, width: int = 30) -> str:
    """Generate an ASCII progress bar."""
    filled = int(round(ratio * width))
    empty = width - filled
    return f"[{'#' * filled}{'.' * empty}]"


def run_audit(transcript_path: Path) -> None:
    """Run full Phase 1 audit pipeline on a transcript file."""
    print("=" * 72)
    print("  ADAPTIVE AGENT MEMORY ENGINE (AAME) - CONTEXT & TOKEN AUDITOR")
    print("=" * 72)
    print(f"\n[+] Target Transcript: {transcript_path}")

    adapter = AntigravityAdapter()
    counter = TokenCounter()
    analyzer = ContextAnalyzer(token_counter=counter)
    cache_analyzer = KVCacheAnalyzer(token_counter=counter)

    # Step 1: Parse
    print("[1/4] Ingesting session transcript...")
    session = adapter.parse(transcript_path)
    print(f"      Parsed {len(session.messages)} steps for session '{session.session_id}'.")

    # Step 2: Analyze tokens and noise
    print("[2/4] Counting tokens & detecting context bloat...")
    report = analyzer.analyze_session(session)

    # Step 3: Analyze KV-Cache Prefix Stability
    print("[3/4] Evaluating KV-Cache prefix continuity...")
    cache_metrics = cache_analyzer.analyze_session(session)

    # Step 4: Display Results
    print("\n" + "-" * 72)
    print("  AUDIT RESULTS & TOKEN METRICS")
    print("-" * 72)
    print(f"  * Total Steps/Messages:     {report.total_messages}")
    print(f"  * Total Context Tokens:     {report.total_tokens:,}")
    print(f"  * Prunable / Noise Tokens:  {report.prunable_tokens:,} ({report.waste_ratio * 100:.1f}%)")
    print(f"  * Noise Bar:                {format_bar(report.waste_ratio)} {report.waste_ratio * 100:.1f}%")
    print(f"  * Clean Core Tokens:        {report.total_tokens - report.prunable_tokens:,}")

    print("\n[+] Token Breakdown by Category:")
    for cat, tokens in sorted(report.category_token_breakdown.items(), key=lambda x: x[1], reverse=True):
        pct = (tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
        print(f"    - {cat:<18}: {tokens:>8,} tokens ({pct:>5.1f}%)")

    print("\n[+] KV-Cache (Prefix Caching) Performance:")
    print(f"  * Estimated Prefix Hit Rate: {cache_metrics.estimated_cache_hit_rate * 100:.1f}%")
    print(f"  * Longest Common Prefix:     {cache_metrics.longest_prefix_tokens:,} tokens")
    if cache_metrics.first_divergence_turn is not None:
        print(f"  * First Cache Invalidation:  Step {cache_metrics.first_divergence_turn}")
    else:
        print("  * Cache Invalidation:        Strict append-only stream (100% prefix retained)")

    if report.top_waste_messages:
        print("\n[!] Top Context Waste Culprits (Recommended for Squash/Prune):")
        for i, m in enumerate(report.top_waste_messages, start=1):
            tool_info = f"[{m.tool_name}] " if m.tool_name else ""
            reason = f"({m.pruning_reason.value if m.pruning_reason else 'unknown'})"
            snippet = m.content[:70].replace("\n", " ") if m.content else ""
            print(f"    {i}. Step {m.step_index:>3} | {m.token_count:>6,} tokens | {tool_info}{reason}")
            if snippet:
                print(f"       Preview: \"{snippet}...\"")

    if report.actionable_recommendations:
        print("\n[*] Recommendations:")
        for rec in report.actionable_recommendations:
            print(f"    -> {rec}")

    print("\n" + "=" * 72)
    print("  Phase 1 Analysis Complete. Deterministic & Zero-cost (0.00 EUR).")
    print("=" * 72 + "\n")


def main() -> None:
    adapter = AntigravityAdapter()
    target_file = None

    if len(sys.argv) > 1:
        custom_path = Path(sys.argv[1])
        if custom_path.exists():
            target_file = custom_path
        else:
            print(f"Error: Path '{custom_path}' does not exist.")
            sys.exit(1)
    else:
        # Auto-discover local Antigravity sessions
        sessions = adapter.discover_sessions()
        if sessions:
            target_file = sessions[0]
            print(f"[i] Auto-discovered {len(sessions)} local Antigravity sessions.")
            print(f"[i] Auditing latest session: {target_file}")
        else:
            print("[!] No local Antigravity sessions found. Provide a path to a transcript.jsonl file.")
            sys.exit(1)

    run_audit(target_file)


if __name__ == "__main__":
    main()
