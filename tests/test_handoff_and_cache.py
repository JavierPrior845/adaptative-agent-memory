"""Unit tests for HandoffGenerator and SessionCache."""

from pathlib import Path
from aame.core.cache_store import SessionCache
from aame.core.handoff import HandoffGenerator
from aame.core.models import MessageCategory, MessageRole, UnifiedMessage, UnifiedSession


def test_handoff_generator_extract_state(sample_session: UnifiedSession):
    generator = HandoffGenerator()
    state = generator.extract_state(sample_session)

    assert state.session_id == sample_session.session_id
    assert "Diseña una arquitectura modular" in state.primary_goal
    assert len(state.key_decisions) >= 1
    assert any("desacoplado" in d.lower() for d in state.key_decisions)


def test_handoff_generator_render_markdown(sample_session: UnifiedSession):
    generator = HandoffGenerator()
    state = generator.extract_state(sample_session)
    md = generator.render_markdown(state)

    assert "# CONTEXT HANDOFF (AAME Checkpoint)" in md
    assert "## 1. Objetivo Principal de la Sesión" in md
    assert "## 2. Decisiones Técnicas Fijadas" in md
    assert "## 3. Vías Descartadas y Errores Resueltos" in md
    assert "## 4. Archivos Activos y Relevantes" in md
    assert "## 5. Siguientes Pasos Operativos" in md


def test_handoff_generate_and_save(sample_session: UnifiedSession, tmp_path: Path):
    generator = HandoffGenerator()
    out_file = tmp_path / "test_handoff.md"
    state, target, content = generator.generate_and_save(sample_session, output_path=out_file)

    assert target == out_file
    assert out_file.is_file()
    assert len(content) > 50


def test_session_cache_lifecycle(sample_session: UnifiedSession, tmp_path: Path):
    cache = SessionCache(cache_dir=tmp_path / "cache")
    assert cache.get_cached_session(sample_session.session_id) is None

    # Save
    success = cache.save_session(sample_session, transcript_mtime=100.0)
    assert success

    # Retrieve
    cached = cache.get_cached_session(sample_session.session_id, transcript_mtime=90.0)
    assert cached is not None
    assert cached["session_id"] == sample_session.session_id
    assert cached["total_tokens"] == sample_session.total_tokens

    # Stale cache check (transcript updated after cache)
    stale = cache.get_cached_session(sample_session.session_id, transcript_mtime=150.0)
    assert stale is None

    # Clear
    removed = cache.clear()
    assert removed == 1
    assert cache.get_cached_session(sample_session.session_id) is None
