"""Context Handoff and State Compression Engine (AAME Squash).

Extracts operative state (goals, technical decisions, active files, pending tasks)
and compiles structured, clean checkpoint artifacts (<1,500 tokens) to eliminate
amnesia when starting fresh agent conversations.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from aame.core.models import MessageCategory, MessageRole, UnifiedMessage, UnifiedSession


class HandoffState(BaseModel):
    """Structured extraction of the operational state from an agent session."""
    session_id: str = Field(description="Source session ID")
    created_at: datetime = Field(default_factory=datetime.now)
    primary_goal: str = Field(default="Tarea general de desarrollo", description="Initial user objective")
    key_decisions: list[str] = Field(default_factory=list, description="Technical decisions and established rules")
    discarded_approaches: list[str] = Field(default_factory=list, description="Errors or paths explored and abandoned")
    active_files: list[str] = Field(default_factory=list, description="Relevant files edited or inspected")
    next_steps: list[str] = Field(default_factory=list, description="Pending tasks or immediate next step")
    clean_token_estimate: int = Field(default=0, description="Estimated token size of the generated handoff")


class HandoffGenerator:
    """Engine that generates concise HANDOFF.md checkpoints from unified sessions."""

    def __init__(self) -> None:
        pass

    def extract_state(self, session: UnifiedSession) -> HandoffState:
        """Analyze messages in session to deterministically synthesize operative state."""
        messages = session.messages
        if not messages:
            return HandoffState(session_id=session.session_id)

        # 1. Primary Goal: First user instruction
        primary_goal = "Desarrollo y refactorización general"
        for m in messages:
            if m.role == MessageRole.USER and m.content:
                clean = self._clean_user_request(m.content)
                if clean:
                    # Take first substantive sentence/paragraph
                    primary_goal = clean.strip().split("\n")[0]
                    break

        # 2. Key Technical Decisions (from ARCHITECTURE messages or assistant summaries)
        key_decisions: list[str] = []
        seen_decisions: set[str] = set()

        for m in messages:
            if m.category == MessageCategory.ARCHITECTURE or (m.role == MessageRole.ASSISTANT and "decisi" in m.content.lower()):
                extracted = self._extract_bullet_points(m.content)
                if not extracted:
                    # If not formatted as bullet points, extract key sentences
                    sentences = [s.strip() for s in re.split(r"[.\n]+", m.content) if len(s.strip()) > 15]
                    extracted = sentences
                for item in extracted:
                    item_clean = item.strip()
                    if len(item_clean) > 15 and item_clean.lower() not in seen_decisions:
                        seen_decisions.add(item_clean.lower())
                        key_decisions.append(item_clean)

        # 3. Discarded Approaches & Errors
        discarded_approaches: list[str] = []
        for m in messages:
            if m.category == MessageCategory.ERROR and m.content:
                first_err_line = self._extract_first_error_line(m.content)
                if first_err_line and first_err_line not in discarded_approaches:
                    discarded_approaches.append(first_err_line)

        # 4. Active Files (from tool calls: replace_file_content, write_to_file, view_file)
        active_files = self._extract_active_files(messages)

        # 5. Next Steps (from final assistant message or pending todos)
        next_steps = self._extract_next_steps(messages)

        return HandoffState(
            session_id=session.session_id,
            created_at=datetime.now(),
            primary_goal=primary_goal,
            key_decisions=key_decisions[:7],  # Keep bounded for token budget
            discarded_approaches=discarded_approaches[:5],
            active_files=active_files[:10],
            next_steps=next_steps[:5],
        )

    def render_markdown(self, state: HandoffState) -> str:
        """Render a HandoffState into an elegant, ready-to-inject Markdown seed."""
        timestamp_str = state.created_at.strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "# CONTEXT HANDOFF (AAME Checkpoint)",
            f"*Sesión de origen: `{state.session_id}` | Generado: {timestamp_str}*",
            "",
            "---",
            "",
            "## 1. Objetivo Principal de la Sesión",
            f"> {state.primary_goal}",
            "",
            "## 2. Decisiones Técnicas Fijadas (No Re-debatir)",
        ]

        if state.key_decisions:
            for dec in state.key_decisions:
                lines.append(f"- [x] {dec}")
        else:
            lines.append("- *Sin restricciones arquitectónicas explícitas registradas.*")

        lines.extend([
            "",
            "## 3. Vías Descartadas y Errores Resueltos (Evitar Repetir)",
        ])

        if state.discarded_approaches:
            for disc in state.discarded_approaches:
                lines.append(f"- ⚠️ {disc}")
        else:
            lines.append("- *Ninguna vía descartada registrada en esta sesión.*")

        lines.extend([
            "",
            "## 4. Archivos Activos y Relevantes",
        ])

        if state.active_files:
            for f in state.active_files:
                lines.append(f"- `{f}`")
        else:
            lines.append("- *No se detectaron archivos de código editados.*")

        lines.extend([
            "",
            "## 5. Siguientes Pasos Operativos",
        ])

        if state.next_steps:
            for step in state.next_steps:
                lines.append(f"- [ ] {step}")
        else:
            lines.append("- [ ] Continuar con la implementación de la siguiente tarea.")

        lines.extend([
            "",
            "---",
            "*Instrucciones para el nuevo agente:* Este documento contiene la verdad operativa condensada "
            "de la sesión previa. Comienza directamente ejecutando los siguientes pasos sin re-analizar "
            "los archivos desde cero ni cuestionar las decisiones fijadas.",
            "",
        ])

        return "\n".join(lines)

    def generate_and_save(
        self,
        session: UnifiedSession,
        output_path: Optional[Path] = None,
    ) -> tuple[HandoffState, Path, str]:
        """Generate handoff and write to disk. Returns (state, path, markdown_content)."""
        state = self.extract_state(session)
        content = self.render_markdown(state)

        if output_path is None:
            # Default to HANDOFF.md in current working directory
            target = Path.cwd() / "HANDOFF.md"
        else:
            target = output_path

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return state, target, content

    @staticmethod
    def _clean_user_request(text: str) -> str:
        """Strip harness XML wrapper tags and metadata."""
        cleaned = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL)
        cleaned = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", cleaned, flags=re.DOTALL)
        match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", cleaned, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return cleaned.strip()

    @staticmethod
    def _extract_bullet_points(text: str) -> list[str]:
        """Extract markdown bullet points from assistant text."""
        points = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ")):
                content = re.sub(r"^[-*0-9.]+\s+", "", line)
                # Remove bold markers for cleaner summaries
                content = content.replace("**", "").strip()
                if len(content) > 10:
                    points.append(content)
        return points

    @staticmethod
    def _extract_first_error_line(text: str) -> Optional[str]:
        """Extract the key error message from an error dump."""
        for line in text.split("\n"):
            line = line.strip()
            if any(k in line for k in ("Error:", "Exception:", "FAILED", "fatal:", "Traceback")):
                return line[:100]
        return None

    @staticmethod
    def _extract_active_files(messages: list[UnifiedMessage]) -> list[str]:
        """Extract file paths mentioned in tool calls or text."""
        files = []
        seen = set()

        for m in messages:
            # Check tool_args
            if m.tool_args and isinstance(m.tool_args, dict):
                for key in ("TargetFile", "AbsolutePath", "SearchPath", "file_path"):
                    val = m.tool_args.get(key)
                    if val and isinstance(val, str) and val not in seen:
                        # Clean up quotes if present
                        val = val.strip('"\'')
                        seen.add(val)
                        files.append(val)

            # Check markdown file mentions in content
            matches = re.findall(r"[`']([a-zA-Z0-9_\-\.\/]+\.[a-zA-Z0-9]+)[`']", m.content)
            for file_candidate in matches:
                if any(file_candidate.endswith(ext) for ext in (".py", ".ts", ".js", ".json", ".md", ".toml", ".rs", ".go")):
                    if file_candidate not in seen:
                        seen.add(file_candidate)
                        files.append(file_candidate)

        return files

    @staticmethod
    def _extract_next_steps(messages: list[UnifiedMessage]) -> list[str]:
        """Find pending next steps from the last messages."""
        for m in reversed(messages):
            if m.role == MessageRole.ASSISTANT and m.content:
                bullets = HandoffGenerator._extract_bullet_points(m.content)
                steps = [b for b in bullets if any(k in b.lower() for k in ("siguiente", "fase", "pendiente", "next", "implementar", "crear"))]
                if steps:
                    return steps
        return []
