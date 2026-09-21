"""Install the bundled skill using the Skills CLI's global directory layout.

Shared-skill agents read ~/.agents/skills directly; other agents receive relative
links. This is an independent installer, with no Node, network, or Skills CLI use.
Path conventions: https://github.com/vercel-labs/skills (skills 1.7.0).
"""

import os
import shutil
from contextlib import ExitStack
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from filelock import FileLock

from . import terminal
from .errors import AgentError

MARKER = ".icloud-agent-installed"
LINKED_AGENTS = {
    "claude-code": "Claude Code",
    "continue": "Continue",
    "goose": "Goose",
    "openclaw": "OpenClaw",
    "openhands": "OpenHands",
    "roo": "Roo Code",
    "windsurf": "Windsurf",
}
AGENT_NAMES = {
    "universal": "Shared skill directory",
    "codex": "Codex",
    "cursor": "Cursor",
    "gemini-cli": "Gemini CLI",
    "opencode": "OpenCode",
    "github-copilot": "GitHub Copilot",
    "cline": "Cline",
    "warp": "Warp",
    **LINKED_AGENTS,
}


def configured_path(variable, default):
    return Path(os.environ.get(variable, "").strip() or default).expanduser().absolute()


def canonical_path():
    return Path.home() / ".agents/skills/icloud-agent"


def codex_home():
    return configured_path("CODEX_HOME", Path.home() / ".codex")


def agent_paths():
    home = Path.home()
    config = configured_path("XDG_CONFIG_HOME", home / ".config")
    openclaw = next(
        (home / name for name in (".openclaw", ".clawdbot", ".moltbot") if (home / name).is_dir()),
        home / ".openclaw",
    )
    return {
        "claude-code": configured_path("CLAUDE_CONFIG_DIR", home / ".claude") / "skills",
        "continue": home / ".continue/skills",
        "goose": config / "goose/skills",
        "openclaw": openclaw / "skills",
        "openhands": home / ".openhands/skills",
        "roo": home / ".roo/skills",
        "windsurf": home / ".codeium/windsurf/skills",
    }


def copy_resources(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            copy_resources(child, target)
        else:
            target.write_bytes(child.read_bytes())


def present(path):
    return path.exists() or path.is_symlink()


def check_destination(path, canonical):
    if not present(path):
        return
    if path.is_symlink():
        if path != canonical and path.resolve() == canonical.resolve():
            return
    elif path.is_dir() and (path / MARKER).is_file():
        return
    raise AgentError("setup_conflict", f"Existing unmanaged skill preserved at {path}.")


def destinations(agents):
    paths = agent_paths()
    unknown = set(agents) - AGENT_NAMES.keys()
    if unknown:
        raise AgentError("invalid_agent", "Unknown skill agent: " + ", ".join(sorted(unknown)))
    canonical = canonical_path()
    links = dict.fromkeys(paths[name] / "icloud-agent" for name in agents if name in paths)
    # A configured agent may itself point at the shared directory.
    links = [path for path in links if path.resolve() != canonical.resolve() or path.is_symlink()]
    for path in links:
        resolved = path.parent.resolve() / path.name
        if canonical.resolve() in resolved.parents or resolved in canonical.resolve().parents:
            raise AgentError(
                "setup_conflict", "Agent skill directories must not contain one another."
            )
    legacy = codex_home() / "skills/icloud-agent"
    if legacy == canonical or legacy in links:
        legacy = None
    for path in [canonical, *links, *([legacy] if legacy else [])]:
        check_destination(path, canonical)
    return canonical, links, legacy


def install(agents=(), *, copy=False):
    """Stage every change, then replace owned paths; roll back a failed commit."""
    canonical, links, legacy = destinations(agents)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(canonical.parent.parent / ".icloud-agent-skills.lock", timeout=1):
        canonical, links, legacy = destinations(agents)
        source = files("icloud_agent").joinpath("resources/plugin/skills/icloud-agent")
        modes = {}
        with ExitStack() as stack:
            changes = []
            for destination in [canonical, *links]:
                destination.parent.mkdir(parents=True, exist_ok=True)
                staging = Path(
                    stack.enter_context(
                        TemporaryDirectory(prefix=".icloud-agent-", dir=destination.parent)
                    )
                )
                replacement = staging / "new"
                mode = "shared" if destination == canonical else "copy"
                if destination != canonical and not copy:
                    try:
                        replacement.symlink_to(
                            os.path.relpath(canonical, destination.parent.resolve()),
                            target_is_directory=True,
                        )
                        mode = "symlink"
                    except (OSError, NotImplementedError):
                        pass
                if mode != "symlink":
                    copy_resources(source, replacement)
                    (replacement / MARKER).touch()
                modes[str(destination)] = mode
                changes.append((destination, replacement, staging / "previous"))
            # Retire the old managed Codex copy so it cannot shadow the shared skill.
            if legacy and present(legacy):
                staging = Path(
                    stack.enter_context(
                        TemporaryDirectory(prefix=".icloud-agent-", dir=legacy.parent)
                    )
                )
                changes.append((legacy, None, staging / "previous"))
            committed = []
            try:
                for destination, replacement, backup in changes:
                    check_destination(destination, canonical)
                    existed = present(destination)
                    if existed:
                        destination.replace(backup)
                    committed.append((destination, backup, existed))
                    if replacement is not None:
                        replacement.replace(destination)
                if legacy and any(destination == legacy for destination, _, _ in committed):
                    # Preserve ownership of MCP registration when retiring its old skill marker.
                    (codex_home() / ".icloud-agent-mcp").touch()
            except BaseException:
                for destination, backup, existed in reversed(committed):
                    if destination.is_symlink():
                        destination.unlink()
                    elif destination.exists():
                        shutil.rmtree(destination)
                    if existed:
                        backup.replace(destination)
                raise
    return {"skill": str(canonical), "agents": list(dict.fromkeys(agents)), "paths": modes}


def choose_agents(out):
    terminal.heading(out, "agent skills")
    out.print("  Shared · Codex, Cursor, Gemini CLI, OpenCode", style="accent")
    out.print("  " + terminal.literal(canonical_path()), style="muted")
    out.print()
    paths = agent_paths()
    return terminal.choose(
        out,
        "Also install for",
        [(name, key) for key, name in LINKED_AGENTS.items()],
        [key for key, path in paths.items() if path.parent.is_dir()],
    )


def installed(out, result):
    out.print()
    out.print("  ✓ Agent skills installed", style="success_bold")
    out.print()
    for path, mode in result["paths"].items():
        out.print("  " + terminal.literal(path), style="accent")
        if mode == "copy":
            out.print("    Copy · update with setup --skills", style="muted")
    out.print()
    out.print("  Start a new agent session to load the skill.", style="muted")
    out.print()


def offer(out):
    """Optional work after authentication has already succeeded and been saved."""
    try:
        action = terminal.pick_one(
            out,
            "Finish setup",
            [("Install agent skills", "install"), ("Finish", "finish")],
            "install",
        )
        if action == "finish":
            return
        agents = choose_agents(out)
        installed(out, install(agents))
    except (EOFError, KeyboardInterrupt):
        out.print("\n  Skill installation skipped.\n", style="muted")
    except Exception as exc:
        out.print("\n  Agent skills were not installed.", style="failure")
        if isinstance(exc, AgentError):
            out.print("  " + terminal.literal(str(exc)))
        out.print("  Retry: icloud-agent setup --skills\n", style="muted")
