"""Persistent Memory Management for AAME across Scopes (Project vs Global).

Manages project-level memory files (.agents/memory/project.json) tracked in Git,
as well as global cross-project preferences (~/.config/aame/global_rules.json).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from aame.utils.paths import get_global_config_dir, get_project_memory_file


class MemoryFact(BaseModel):
    """An explicit fact, architectural guideline, or constraint."""
    id: str = Field(description="Deterministic slug or unique identifier")
    category: str = Field(default="architecture", description="Semantic tag: architecture, tech_stack, convention")
    fact: str = Field(description="The concrete rule, decision, or fact statement")
    created_at: datetime = Field(default_factory=datetime.now)
    source_session_id: Optional[str] = Field(default=None, description="Session that established this fact")
    author: Optional[str] = Field(default="user", description="Author: user | agent")


class ScopeMemory(BaseModel):
    """Memory representation for a specific scope (Project or Global)."""
    version: str = Field(default="1.0.0")
    scope: str = Field(description="Scope name: 'project' | 'global'")
    updated_at: datetime = Field(default_factory=datetime.now)
    facts: list[MemoryFact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_fact(self, fact: MemoryFact) -> None:
        """Add or replace fact by ID."""
        self.facts = [f for f in self.facts if f.id != fact.id]
        self.facts.append(fact)
        self.updated_at = datetime.now()

    def remove_fact(self, fact_id: str) -> bool:
        """Remove fact by ID. Returns True if found and removed."""
        initial_len = len(self.facts)
        self.facts = [f for f in self.facts if f.id != fact_id]
        if len(self.facts) < initial_len:
            self.updated_at = datetime.now()
            return True
        return False

    def get_fact(self, fact_id: str) -> Optional[MemoryFact]:
        """Find a fact by its ID."""
        for f in self.facts:
            if f.id == fact_id:
                return f
        return None


class PersistentMemoryManager:
    """Manages reading, writing, and consolidating memory across project and global scopes."""

    def __init__(self, repo_root: Optional[Path] = None, global_dir: Optional[Path] = None) -> None:
        self.project_file = get_project_memory_file(repo_root)
        self.global_dir = global_dir or get_global_config_dir()
        self.global_file = self.global_dir / "global_rules.json"

    def load_project_memory(self) -> ScopeMemory:
        """Load project-level memory from .agents/memory/project.json."""
        if not self.project_file.is_file():
            return ScopeMemory(scope="project")

        try:
            with self.project_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return ScopeMemory.model_validate(data)
        except Exception:
            return ScopeMemory(scope="project")

    def save_project_memory(self, memory: ScopeMemory) -> Path:
        """Persist project-level memory to disk (tracked in Git)."""
        self.project_file.parent.mkdir(parents=True, exist_ok=True)
        memory.updated_at = datetime.now()
        with self.project_file.open("w", encoding="utf-8") as f:
            json.dump(memory.model_dump(mode="json"), f, indent=2, default=str)
        return self.project_file

    def load_global_memory(self) -> ScopeMemory:
        """Load user-global preferences from ~/.config/aame/global_rules.json."""
        if not self.global_file.is_file():
            return ScopeMemory(scope="global")

        try:
            with self.global_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return ScopeMemory.model_validate(data)
        except Exception:
            return ScopeMemory(scope="global")

    def save_global_memory(self, memory: ScopeMemory) -> Path:
        """Persist user-global rules to disk."""
        self.global_file.parent.mkdir(parents=True, exist_ok=True)
        memory.updated_at = datetime.now()
        with self.global_file.open("w", encoding="utf-8") as f:
            json.dump(memory.model_dump(mode="json"), f, indent=2, default=str)
        return self.global_file

    def add_project_fact(
        self,
        fact_id: str,
        fact: str,
        category: str = "architecture",
        session_id: Optional[str] = None,
    ) -> MemoryFact:
        """Convenience method to register a fact in project memory."""
        mem = self.load_project_memory()
        item = MemoryFact(
            id=fact_id,
            category=category,
            fact=fact,
            source_session_id=session_id,
        )
        mem.add_fact(item)
        self.save_project_memory(mem)
        return item

    def render_consolidated_prompt(self) -> str:
        """Combine global and project facts into a compact prompt section for new chats."""
        global_mem = self.load_global_memory()
        project_mem = self.load_project_memory()

        lines = ["# PROJECT & SYSTEM MEMORY"]

        if global_mem.facts:
            lines.append("\n## Global Preferences:")
            for f in global_mem.facts:
                lines.append(f"- [{f.category}] {f.fact}")

        if project_mem.facts:
            lines.append("\n## Architectural Decisions & Project Rules:")
            for f in project_mem.facts:
                lines.append(f"- [{f.category}] {f.fact}")

        if not global_mem.facts and not project_mem.facts:
            lines.append("\n*No persistent facts recorded yet.*")

        return "\n".join(lines)
