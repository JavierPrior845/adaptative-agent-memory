---
name: harness-adapter-craft
description: Guide and patterns for creating new agent harness adapters in AAME. Use when adding support for new AI coding tools, agent environments, or IDEs (such as Cursor, Cline, Roo-Code, OpenCode, Codex, Aider) to ingest conversation transcripts, parse messages into the UnifiedMessage model, and enable token auditing, KV-cache metrics, and context handoffs.
---

# Harness Adapter Craft (Extending AAME)

This guide documents the architecture, patterns, and conventions for creating new **Agent Harness Adapters** in the **Adaptive Agent Memory Engine (AAME)**.

---

## 1. Core Architecture & Philosophy

AAME decouples proprietary agent log formats (JSONL, SQLite, JSON dumps) from the core analytical and UI engines using the **Adapter Pattern**.

```
[ Proprietary Harness Data ]
   (Antigravity transcript.jsonl / Claude Code sessions / Cursor state.vscdb / Cline JSON)
                                │
                                ▼
                   [ Specific HarnessAdapter ]
             (Implements can_handle, parse, discover)
                                │
                                ▼
                       [ UnifiedSession ]
                ┌───────────────┴───────────────┐
                ▼                               ▼
       [ ContextAnalyzer ]             [ KVCacheAnalyzer ]
       (Noise detection,               (Prefix stability,
        categorization, pruning)        cache hit simulation)
                │                               │
                ▼                               ▼
         [ HANDOFF.md ]                  [ Textual Cockpit ]
```

### Invariants:
1. **Never mutate original files**: Adapters only read transcripts and conversation logs.
2. **Streaming & Resilient**: Large conversation transcripts (hundreds of steps) must be streamed or loaded without blocking or exhausting memory.
3. **Decoupled Roles**: The adapter maps proprietary events to `MessageRole` (`USER`, `ASSISTANT`, `TOOL`, `SYSTEM`).
4. **Zero-cost Execution**: Never make external network calls or LLM API requests inside an adapter.

---

## 2. Implementing the `HarnessAdapter` Interface

Every new adapter must inherit from `HarnessAdapter` defined in `src/aame/adapters/base.py`:

```python
from pathlib import Path
from typing import Optional
from aame.adapters.base import HarnessAdapter
from aame.core.models import UnifiedMessage, UnifiedSession

class CustomAgentAdapter(HarnessAdapter):
    @property
    def name(self) -> str:
        """Unique lowercase identifier for the harness."""
        return "my_agent"

    def can_handle(self, path: Path) -> bool:
        """Check if this path represents a session or directory for this harness."""
        if path.is_file():
            return "my_agent" in path.name and path.suffix in (".json", ".jsonl")
        if path.is_dir():
            return (path / ".my_agent_logs").is_dir()
        return False

    def parse(self, path: Path) -> UnifiedSession:
        """Parse target path into a normalized UnifiedSession."""
        ...

    def discover_sessions(self, base_dir: Optional[Path] = None) -> list[Path]:
        """Automatically find all sessions on the current machine."""
        ...
```

---

## 3. Normalization Strategy: Mapping to `UnifiedMessage`

The adapter must normalize raw steps into `UnifiedMessage`:

| Raw Harness Concept | `UnifiedMessage.role` | `UnifiedMessage.category` | Notes |
| :--- | :--- | :--- | :--- |
| User prompt / Request | `MessageRole.USER` | `MessageCategory.USER_INSTRUCTION` | Clean wrapper tags (`<USER_REQUEST>`) if present |
| Agent text response | `MessageRole.ASSISTANT` | `MessageCategory.GENERAL` | `ContextAnalyzer` will refine to `ARCHITECTURE` or `SIDE_QUEST` |
| Agent tool invocation | `MessageRole.ASSISTANT` | `MessageCategory.TOOL_CALL` | Populate `tool_name` and `tool_args` |
| Command/Tool execution output | `MessageRole.TOOL` | `MessageCategory.TOOL_OUTPUT` | If exit code != 0, set to `MessageCategory.ERROR` |
| System instructions / rules | `MessageRole.SYSTEM` | `MessageCategory.SYSTEM_PROMPT` | Knowledge files, rules, base instructions |

### Concrete Normalization Example

```python
from datetime import datetime
from aame.core.models import MessageCategory, MessageRole, UnifiedMessage

def normalize_step(raw_data: dict, session_id: str, step_index: int) -> UnifiedMessage:
    role_str = raw_data.get("role", "").lower()
    content = raw_data.get("content", "")
    
    # 1. Determine role
    if role_str == "user":
        role = MessageRole.USER
        category = MessageCategory.USER_INSTRUCTION
    elif role_str == "assistant":
        role = MessageRole.ASSISTANT
        category = MessageCategory.GENERAL
    elif role_str == "tool":
        role = MessageRole.TOOL
        category = MessageCategory.TOOL_OUTPUT
    else:
        role = MessageRole.SYSTEM
        category = MessageCategory.SYSTEM_PROMPT

    # 2. Extract tool metadata if applicable
    tool_name = raw_data.get("tool_name")
    tool_args = raw_data.get("tool_args")
    exit_code = raw_data.get("exit_code")

    if exit_code is not None and exit_code != 0:
        category = MessageCategory.ERROR

    # 3. Parse timestamp
    timestamp = None
    if "timestamp" in raw_data:
        try:
            timestamp = datetime.fromisoformat(raw_data["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            pass

    return UnifiedMessage(
        id=f"{session_id}-step-{step_index}",
        step_index=step_index,
        role=role,
        category=category,
        content=content,
        token_count=0,  # Computed automatically by TokenCounter
        is_prunable=False,
        timestamp=timestamp,
        tool_name=tool_name,
        tool_args=tool_args,
        exit_code=exit_code,
        metadata={"raw_source": raw_data},
    )
```

---

## 4. Multi-Format Handling: JSONL vs SQLite

Different agent tools store transcripts in different backends:

### A. Streaming JSON Lines (e.g. Antigravity, Claude Code)
Use the built-in helper `self.stream_jsonl(path)` on `HarnessAdapter`:
```python
for step_data in self.stream_jsonl(transcript_file):
    msg = normalize_step(step_data, session_id, step_index)
    unified_messages.append(msg)
```
*Note: `stream_jsonl` handles encoding fallbacks and skips malformed JSON lines without crashing.*

### B. SQLite Databases (e.g. Cursor `state.vscdb`)
For SQLite stores:
1. Open in **read-only URI mode** (`sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`).
2. Avoid table locks while the IDE is running.
3. Query bubbles / message tables and stream rows into `UnifiedMessage`.

---

## 5. Registering the New Adapter in AAME

To make the new adapter active in both the CLI and Cockpit TUI:

1. **Export in `src/aame/adapters/__init__.py`**:
   ```python
   from aame.adapters.my_agent import MyAgentAdapter
   
   __all__ = [
       ...,
       "MyAgentAdapter",
   ]
   ```

2. **Register in CLI (`src/aame/cli/app.py`)**:
   Add the adapter to `_resolve_session_path` and `list_sessions`:
   ```python
   adapters = [AntigravityAdapter(), ClaudeCodeAdapter(), MyAgentAdapter()]
   ```

3. **Register in TUI Cockpit (`src/aame/tui/widgets/session_list.py`)**:
   Include it in `refresh_sessions()` so the sidebar discovers both Antigravity, Claude Code, and your new agent automatically.

---

## 6. Testing Checklist (`pytest`)

Always include a dedicated test file in `tests/test_<adapter_name>_adapter.py`:

```python
import pytest
from pathlib import Path
from aame.adapters.my_agent import MyAgentAdapter
from aame.core.models import MessageRole

def test_can_handle(tmp_path: Path):
    adapter = MyAgentAdapter()
    sample_file = tmp_path / "my_agent_session.jsonl"
    sample_file.touch()
    assert adapter.can_handle(sample_file)

def test_parse_normalized_session(tmp_path: Path):
    adapter = MyAgentAdapter()
    # Write synthetic log with user, assistant and tool messages
    ...
    session = adapter.parse(sample_log)
    assert len(session.messages) > 0
    assert session.messages[0].role == MessageRole.USER
    assert session.harness_name == "my_agent"
```
Run `pytest` to guarantee 100% test pass rate across all adapters.
