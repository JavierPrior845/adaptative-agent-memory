"""Unit tests for AntigravityAdapter."""

from pathlib import Path
from aame.adapters.antigravity import AntigravityAdapter
from aame.core.models import MessageCategory, MessageRole


def test_can_handle(synthetic_transcript_path: Path):
    adapter = AntigravityAdapter()
    assert adapter.can_handle(synthetic_transcript_path)
    # Check session directory
    session_dir = synthetic_transcript_path.parent.parent.parent
    assert adapter.can_handle(session_dir)


def test_parse_synthetic_transcript(synthetic_transcript_path: Path):
    adapter = AntigravityAdapter()
    session = adapter.parse(synthetic_transcript_path)

    assert session.session_id == "conv-uuid-1234"
    assert session.harness_name == "antigravity"
    assert len(session.messages) == 4

    # Message 0: User request
    m0 = session.messages[0]
    assert m0.role == MessageRole.USER
    assert m0.category == MessageCategory.USER_INSTRUCTION
    assert "<USER_REQUEST>" in m0.content

    # Message 1: Model tool call
    m1 = session.messages[1]
    assert m1.role == MessageRole.ASSISTANT
    assert m1.category == MessageCategory.TOOL_CALL
    assert m1.tool_name == "run_command"

    # Message 2: Tool output
    m2 = session.messages[2]
    assert m2.role == MessageRole.TOOL
    assert m2.category == MessageCategory.TOOL_OUTPUT
    assert m2.exit_code == 0


def test_stream_jsonl_malformed_resilience(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt_transcript.jsonl"
    with open(corrupt_file, "w", encoding="utf-8") as f:
        f.write('{"step_index": 0, "type": "USER_INPUT"}\n')
        f.write("MALFORMED JSON LINE NOT PARSABLE\n")
        f.write('{"step_index": 1, "type": "PLANNER_RESPONSE"}\n')

    adapter = AntigravityAdapter()
    items = list(adapter.stream_jsonl(corrupt_file))
    # Should yield the 2 valid objects without crashing
    assert len(items) == 2
    assert items[0]["step_index"] == 0
    assert items[1]["step_index"] == 1


def test_discover_sessions(tmp_path: Path, synthetic_transcript_path: Path):
    adapter = AntigravityAdapter()
    # Discover in the tmp_path / brain
    brain_dir = synthetic_transcript_path.parent.parent.parent.parent
    found = adapter.discover_sessions(base_dir=brain_dir)
    assert len(found) >= 1
    assert any("transcript.jsonl" in str(p) for p in found)
