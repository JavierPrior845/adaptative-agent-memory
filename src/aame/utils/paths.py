"""Cross-platform directory and path resolution utilities for AAME."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def get_user_home() -> Path:
    """Return user home directory reliably across platforms."""
    return Path.home()


def get_global_config_dir() -> Path:
    """Return platform-standard directory for AAME global configurations.
    
    Linux:   ~/.config/aame
    macOS:   ~/Library/Application Support/aame
    Windows: %APPDATA%\aame
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "aame"
        return get_user_home() / "AppData" / "Roaming" / "aame"
    elif sys.platform == "darwin":
        return get_user_home() / "Library" / "Application Support" / "aame"
    else:
        # Linux / Unix
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "aame"
        return get_user_home() / ".config" / "aame"


def get_antigravity_brain_dir() -> Optional[Path]:
    """Find Antigravity brain directory on current operating system."""
    home = get_user_home()
    candidates = [
        home / ".gemini" / "antigravity-ide" / "brain",
        home / ".antigravity" / "brain",
    ]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "antigravity-ide" / "brain")
    elif sys.platform == "darwin":
        candidates.append(home / "Library" / "Application Support" / "antigravity-ide" / "brain")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def get_project_memory_file(repo_root: Optional[Path] = None) -> Path:
    """Return standard location for project-level persistent memory in git repository.
    
    Default: <repo_root>/.agents/memory/project.json
    """
    root = repo_root or Path.cwd()
    return root / ".agents" / "memory" / "project.json"
