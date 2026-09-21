"""Install bundled agent integration without a source checkout."""

import json
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from platformdirs import user_data_path

from . import agent_skills
from .agent_skills import copy_resources
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


def setup(codex=False, *, skills=False, agents=(), copy=False):
    executable = executable_path()
    base = user_data_path("icloud-agent", appauthor=False)
    codex_home = agent_skills.codex_home()
    marker = codex_home / ".icloud-agent-mcp"
    old_marker = codex_home / "skills/icloud-agent/.icloud-agent-installed"
    codex_command = shutil.which("codex")
    if codex:
        if not codex_command:
            raise AgentError("codex_missing", "Install Codex and put its CLI on PATH, then retry.")
        agent_skills.destinations(agents)
        existing = subprocess.run(
            [codex_command, "mcp", "get", "icloud-agent", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        # MCP ownership is separate from the skill shared by all local agents.
        legacy = codex_home == Path.home() / ".codex" and (base / "codex-managed").is_file()
        if existing.returncode == 0 and not (marker.is_file() or old_marker.is_file() or legacy):
            raise AgentError(
                "setup_conflict", "Existing unmanaged icloud-agent MCP entry preserved."
            )
    if skills:
        agent_skills.destinations(agents)
    plugin = base / "plugin/icloud-agent"
    copy_resources(files("icloud_agent").joinpath("resources/plugin"), plugin)
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {"mcpServers": {"icloud-agent": {"command": str(executable), "args": ["mcp"]}}},
            indent=2,
        )
        + "\n"
    )
    skill_result = agent_skills.install(agents, copy=copy) if codex or skills else None
    if codex:
        result = subprocess.run(
            [codex_command, "mcp", "add", "icloud-agent", "--", str(executable), "mcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AgentError("setup_failed", "Codex registration failed. Check codex mcp list.")
        codex_home.mkdir(parents=True, exist_ok=True)
        marker.touch()
    return {
        "executable": str(executable),
        "plugin": str(plugin),
        "codex_registered": codex,
        "skill": skill_result["skill"] if skill_result else None,
        "skills": skill_result,
        "next": "Run icloud-agent auth login in your terminal, then restart your agent client.",
    }
