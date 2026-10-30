---
name: modern-tui-craft
description: Design and build modern, visually polished Terminal User Interfaces (TUIs) using Textual and Rich, inspired by modern CLI tools like Claude Code and OpenCode. Use when building terminal apps, TUIs, dashboard cockpits, or styling Textual layouts with custom palettes, token bars, and clean typography.
---

# Modern TUI Craft (Textual & Rich)

Guidelines, aesthetics, and implementation patterns to build modern terminal applications that look like premium developer tools (Claude Code, OpenCode, Lazygit) rather than primitive 90s ASCII box-drawing interfaces.

## Core Philosophy

1. **Restraint over ASCII borders**: Modern terminal apps do not box every single label with `+---+`. Use subtle background contrasts, minimal single-line dividers, or pure whitespace padding to delineate visual boundaries.
2. **Strict color palette (Muted Dark Base + Accent)**:
   - Dark background: Deep slate or charcoal (`#0D1117`, `#161B22`, `#1E1E2E`).
   - Text hierarchy: High contrast for headers (`#F0F6FC`), muted gray for secondary/metadata (`#8B949E`), dim for timestamps/indices (`#484F58`).
   - Accents: Use semantic colors with purpose (e.g., Cyan/Teal `#58A6FF` o `#39C5BB` para tokens/selección activa, Púrpura `#BC8CFF` para salidas de herramientas, Verde `#3FB950` para checkpoints/éxito).
3. **Smooth visual glyphs**: Replace raw ASCII (`#`, `*`, `|`) with modern unicode block elements:
   - Horizontal bars: `█`, `▆`, `▅`, `▄`, `▃`, `▂` o bloques parciales horizontales `▏▎▍▌▋▊▉█`.
   - Indicators: `●` (activo), `○` (inactivo/espera), `◆` (tool call), `✔` / `✖`.

---

## 1. Textual Architecture for Cockpit Apps

Patrón para aplicaciones interactivas con Textual (como tu visor de sesiones y tokens):

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static

class TokenCockpitApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("q", "quit", "Salir"),
        ("p", "prune_noise", "Podar Ruido"),
        ("s", "squash_session", "Squash/Handoff"),
        ("tab", "focus_next", "Cambiar Panel"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="sidebar"):
                yield Static(" SESIONES RECIENTES ", classes="pane-title")
                yield SessionListView(id="session-list")
            with Vertical(id="workspace"):
                yield Static(" DETALLE DE TURNO & TOKENS ", classes="pane-title")
                yield TokenMetricsView(id="token-metrics")
                yield MessageDetailView(id="message-detail")
        yield Footer()

```

---

## 2. Textual CSS (TCSS) Styling Guide

Archivo `.tcss` para desacoplar el diseño visual del código Python:

```css
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

Header {
    background: #161b22;
    color: #58a6ff;
    dock: top;
    height: 1;
}

Footer {
    background: #161b22;
    color: #8b949e;
    dock: bottom;
}

#main-layout {
    height: 1fr;
}

#sidebar {
    width: 32%;
    background: #13171f;
    border-right: solid #21262d;
    padding: 1 1;
}

#workspace {
    width: 68%;
    padding: 1 2;
}

.pane-title {
    color: #58a6ff;
    text-style: bold;
    margin-bottom: 1;
    border-bottom: heavy #30363d;
}

ListItem:hover {
    background: #1f242c;
}

ListItem.-selected {
    background: #238636;
    color: #ffffff;
    text-style: bold;
}

```

---

## 3. Rendering Token Bars without Clunky ASCII

Generador de barras fluidas con caracteres fraccionarios Unicode:

```python
def render_token_meter(used: int, limit: int = 128_000, width: int = 24) -> str:
    ratio = min(max(used / limit, 0.0), 1.0)
    filled_blocks = int(ratio * width)
    remainder = (ratio * width) - filled_blocks

    sub_blocks = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
    sub_index = int(remainder * len(sub_blocks))
    partial_char = sub_blocks[sub_index] if filled_blocks < width else ""

    bar = ("█" * filled_blocks) + partial_char
    bar = bar.ljust(width, "░")
    return f"{bar} {used:,} / {limit:,} ({ratio:.1%})"

```

---

## 4. Key UX Conventions

* **Atajos directos en el Footer**: Mantén los controles visibles y contextualmente actualizados.
* **Filtros rápidos**: Emplea búsqueda dinámica o filtrado difuso sobre listas de mensajes y sesiones.
* **Micro-feedback**: Emplea `self.notify(...)` para avisar de acciones completadas (como podas o generación de handoffs) sin interrumpir el flujo con cuadros modales.

```


```