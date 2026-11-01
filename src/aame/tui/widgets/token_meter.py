"""Fluid Unicode token meter and KV-cache visualization widget."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from aame.core.models import CachePrefixMetrics, NoiseReport


def render_token_meter(used: int, limit: int = 128_000, width: int = 24) -> str:
    """Render a smooth Unicode bar with fractional sub-blocks (from modern-tui-craft)."""
    ratio = min(max(used / limit, 0.0), 1.0)
    filled_blocks = int(ratio * width)
    remainder = (ratio * width) - filled_blocks

    sub_blocks = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
    sub_index = int(remainder * len(sub_blocks))
    partial_char = sub_blocks[sub_index] if filled_blocks < width else ""

    bar = ("█" * filled_blocks) + partial_char
    bar = bar.ljust(width, "░")
    return f"{bar} {used:,} / {limit:,} ({ratio:.1%})"


class TokenMeterWidget(Static):
    """Widget displaying context metrics, KV-Cache continuity and noise ratio."""

    def update_metrics(
        self,
        report: NoiseReport,
        cache_metrics: CachePrefixMetrics,
        context_limit: int = 128_000,
    ) -> None:
        """Update display with analyzed session metrics."""
        text = Text()

        # Line 1: Header / Title
        text.append("● CONTEXT & TOKEN COCKPIT", style="bold #58a6ff")
        text.append(f"  |  Total Steps: {report.total_messages}", style="#8b949e")
        text.append("\n")

        # Line 2: Context Fill Meter
        used = report.total_tokens
        ratio = min(max(used / context_limit, 0.0), 1.0)
        filled = int(ratio * 28)
        bar_color = "#3fb950" if ratio < 0.4 else ("#d29922" if ratio < 0.75 else "#f85149")

        text.append("Context Load : ", style="bold #c9d1d9")
        sub_blocks = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
        remainder = (ratio * 28) - filled
        partial = sub_blocks[int(remainder * len(sub_blocks))] if filled < 28 else ""
        bar_str = ("█" * filled) + partial
        text.append(bar_str, style=bar_color)
        text.append("░" * (28 - len(bar_str)), style="#30363d")
        text.append(f"  {used:,} / {context_limit:,} tokens ({ratio:.1%})\n", style="bold #f0f6fc")

        # Line 3: Noise Ratio Meter
        waste_ratio = report.waste_ratio
        noise_filled = int(waste_ratio * 28)
        text.append("Noise Ratio  : ", style="bold #c9d1d9")
        n_sub_idx = int(((waste_ratio * 28) - noise_filled) * len(sub_blocks))
        n_partial = sub_blocks[n_sub_idx] if noise_filled < 28 else ""
        n_bar_str = ("█" * noise_filled) + n_partial
        text.append(n_bar_str, style="#d29922")
        text.append("░" * (28 - len(n_bar_str)), style="#30363d")
        text.append(f"  {report.prunable_tokens:,} discardable ({waste_ratio:.1%})\n", style="#d29922")

        # Line 4: KV-Cache Continuity & Clean core
        hit_pct = cache_metrics.estimated_cache_hit_rate * 100
        text.append("Prefix Cache : ", style="bold #c9d1d9")
        text.append(f"{hit_pct:.1f}% hit rate", style="bold #3fb950" if hit_pct > 80 else "#d29922")
        text.append(f"  |  Stable Prefix: {cache_metrics.longest_prefix_tokens:,} tokens", style="#8b949e")
        clean_core = report.total_tokens - report.prunable_tokens
        text.append(f"  |  Clean Core: {clean_core:,} tokens", style="bold #58a6ff")

        self.update(text)
