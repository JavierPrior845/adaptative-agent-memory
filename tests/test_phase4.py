"""Unit tests for ClaudeCodeAdapter and PersistentMemoryManager."""

import json
from pathlib import Path
import pytest

from aame.adapters.claude_code import ClaudeCodeAdapter
from aame.core.memory_manager import MemoryFact, PersistentMemoryManager, ScopeMemory
from aame.core.models import MessageCategory, MessageRole


@pytest.fixture
def synthetic_claude_log(tmp_path: Path) -> Path:
    """Create a synthetic Claude Code history.jsonl file."""
    claude_dir = tmp_path / ".claude" / "sessions"
    claude_dir.mkdir(parents=True)
    log_file = claude_dir / "session_abc123.jsonl"

    entries = [
        {
            "role": "user",
            "content": "Construye un adaptador para Claude Code en AAME",
            "created_at": "2026-11-01T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Entendido, implementaré ClaudeCodeAdapter."},
                {"type": "tool_use", "name": "WriteFile", "input": {"path": "adapter.py"}},
            ],
            "created_at": "2026-11-01T10:00:05Z",
        },
        {
            "role": "tool",
            "content": [{"type": "tool_result", "content": "File written successfully."}],
            "created_at": "2026-11-01T10:00:07Z",
        },
    ]

    with open(log_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    return log_file


def test_claude_adapter_can_handle(synthetic_claude_log: Path):
    adapter = ClaudeCodeAdapter()
    assert adapter.can_handle(synthetic_claude_log)
    assert adapter.can_handle(synthetic_claude_log.parent.parent)


def test_claude_adapter_parse(synthetic_claude_log: Path):
    adapter = ClaudeCodeAdapter()
    session = adapter.parse(synthetic_claude_log)

    assert session.session_id == "session_abc123"
    assert session.harness_name == "claude_code"
    assert len(session.messages) == 3

    # Check user message
    assert session.messages[0].role == MessageRole.USER
    assert "Construye un adaptador" in session.messages[0].content

    # Check assistant tool use
    assert session.messages[1].role == MessageRole.ASSISTANT
    assert session.messages[1].tool_name == "WriteFile"

    # Check tool output
    assert session.messages[2].role == MessageRole.TOOL
    assert session.messages[2].category == MessageCategory.TOOL_OUTPUT


def test_persistent_memory_manager_lifecycle(tmp_path: Path):
    repo_root = tmp_path / "repo"
    global_dir = tmp_path / "global_config"

    mgr = PersistentMemoryManager(repo_root=repo_root, global_dir=global_dir)

    # Initial load is empty
    proj_mem = mgr.load_project_memory()
    assert len(proj_mem.facts) == 0

    # Add project fact
    fact = mgr.add_project_fact(
        fact_id="arch-db-001",
        fact="Se decide utilizar SQLite y JSON en frío sin base de datos externa para coste cero",
        category="architecture",
    )
    assert fact.id == "arch-db-001"

    # Reload and verify
    reloaded = mgr.load_project_memory()
    assert len(reloaded.facts) == 1
    assert reloaded.facts[0].id == "arch-db-001"

    # Add global preference
    glob_mem = mgr.load_global_memory()
    glob_mem.add_fact(MemoryFact(id="pref-theme", category="ui", fact="Prefiere temas oscuros Charcoal/Slate"))
    mgr.save_global_memory(glob_mem)

    # Test consolidated prompt
    prompt = mgr.render_consolidated_prompt()
    assert "PROJECT & SYSTEM MEMORY" in prompt
    assert "arch-db-001" not in prompt  # Fact IDs not in bullet text
    assert "Se decide utilizar SQLite" in prompt
    assert "Prefiere temas oscuros" in prompt

    # Remove fact
    removed = reloaded.remove_fact("arch-db-001")
    assert removed
    mgr.save_project_memory(reloaded)
    assert len(mgr.load_project_memory().facts) == 0
