"""Install bundled agent integration without a source checkout."""

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from platformdirs import user_data_path

from .errors import AgentError


def executable_path():
    # Keep Homebrew's opt symlink stable across upgrades; do not resolve it to Cellar.
    candidate = Path(sys.argv[0]).absolute()
    if candidate.name in ("icloud-agent", "icloud-agent.exe") and candidate.is_file():
        return candidate
    candidate = Path(sys.executable).parent / (
        "icloud-agent.exe" if sys.platform == "win32" else "icloud-agent"
    )
    if not candidate.is_file():
        raise AgentError("setup_failed", "Run setup using the installed icloud-agent command.")
    return candidate


def copy_resources(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            copy_resources(child, target)
        else:
            target.write_bytes(child.read_bytes())


def setup(codex=False):
    executable = executable_path()
    base = user_data_path("icloud-agent", appauthor=False)
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    skill = codex_home / "skills/icloud-agent"
    marker = skill / ".icloud-agent-installed"
    codex_command = shutil.which("codex")
    if codex:
        if not codex_command:
            raise AgentError("codex_missing", "Install Codex and put its CLI on PATH, then retry.")
        if skill.exists() and not marker.is_file():
            raise AgentError("setup_conflict", f"Existing unmanaged skill preserved at {skill}.")
        existing = subprocess.run(
            [codex_command, "mcp", "get", "icloud-agent", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        # A managed skill in this CODEX_HOME identifies registrations this tool owns.
        # The legacy default installer also wrote a marker in the application data directory.
        legacy = codex_home == Path.home() / ".codex" and (base / "codex-managed").is_file()
        if existing.returncode == 0 and not (marker.is_file() or legacy):
            raise AgentError(
                "setup_conflict", "Existing unmanaged icloud-agent MCP entry preserved."
            )
    plugin = base / "plugin/icloud-agent"
    copy_resources(files("icloud_agent").joinpath("resources/plugin"), plugin)
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {"mcpServers": {"icloud-agent": {"command": str(executable), "args": ["mcp"]}}},
            indent=2,
        )
        + "\n"
    )
    if codex:
        result = subprocess.run(
            [codex_command, "mcp", "add", "icloud-agent", "--", str(executable), "mcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AgentError("setup_failed", "Codex registration failed. Check codex mcp list.")
        copy_resources(
            files("icloud_agent").joinpath("resources/plugin/skills/icloud-agent"), skill
        )
        marker.touch()
    return {
        "executable": str(executable),
        "plugin": str(plugin),
        "codex_registered": codex,
        "skill": str(skill) if codex else None,
        "next": "Run icloud-agent auth login in your terminal, then restart your agent client.",
    }
