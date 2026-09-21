import io
from pathlib import Path

import pytest
from rich.console import Console

from icloud_agent import agent_skills, terminal
from icloud_agent.errors import AgentError


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def owned(path, text="old skill"):
    path.mkdir(parents=True)
    (path / agent_skills.MARKER).touch()
    (path / "SKILL.md").write_text(text)
    return path


def test_shared_agents_use_canonical_and_other_agents_get_relative_links(home):
    result = agent_skills.install(["codex", "cursor", "claude-code", "windsurf", "claude-code"])
    canonical = home / ".agents/skills/icloud-agent"
    assert "iCloud Mail and Calendar" in (canonical / "SKILL.md").read_text()
    assert result["paths"][str(canonical)] == "shared"
    assert len(result["paths"]) == 3
    for path in (
        home / ".claude/skills/icloud-agent",
        home / ".codeium/windsurf/skills/icloud-agent",
    ):
        assert path.is_symlink() and not path.readlink().is_absolute()
        assert path.resolve() == canonical
    assert not (home / ".cursor").exists()
    assert not (home / ".codex").exists()


def test_custom_agent_directories_and_explicit_copies(home, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / "custom-claude"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "custom-config"))
    result = agent_skills.install(["claude-code", "goose"], copy=True)
    canonical = home / ".agents/skills/icloud-agent"
    for path in (
        home / "custom-claude/skills/icloud-agent",
        home / "custom-config/goose/skills/icloud-agent",
    ):
        assert not path.is_symlink()
        assert result["paths"][str(path)] == "copy"
        assert (path / "SKILL.md").read_bytes() == (canonical / "SKILL.md").read_bytes()


def test_missing_symlink_permission_falls_back_to_copy(home, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionError("symlinks unavailable")

    monkeypatch.setattr(Path, "symlink_to", deny)
    result = agent_skills.install(["claude-code"])
    destination = home / ".claude/skills/icloud-agent"
    assert result["paths"][str(destination)] == "copy"
    assert (destination / "SKILL.md").is_file()


@pytest.mark.parametrize(
    "destination",
    [".agents/skills/icloud-agent", ".claude/skills/icloud-agent", ".codex/skills/icloud-agent"],
)
def test_unmanaged_skill_conflict_is_preflighted_before_any_install(home, destination):
    path = home / destination
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("user-owned skill")
    before = sorted(str(p.relative_to(home)) for p in home.rglob("*"))
    with pytest.raises(AgentError, match="unmanaged skill"):
        agent_skills.install(["claude-code"])
    assert (path / "SKILL.md").read_text() == "user-owned skill"
    assert sorted(str(p.relative_to(home)) for p in home.rglob("*")) == before


def test_unmanaged_symlink_target_is_never_rewritten(home):
    elsewhere = owned(home / "unrelated")
    canonical = home / ".agents/skills/icloud-agent"
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(AgentError, match="unmanaged skill"):
        agent_skills.install()
    assert canonical.is_symlink()
    assert (elsewhere / "SKILL.md").read_text() == "old skill"


def test_updates_replace_stale_files_and_keep_agent_links_working(home):
    agent_skills.install(["claude-code"])
    canonical = home / ".agents/skills/icloud-agent"
    (canonical / "obsolete.md").write_text("old version")
    agent_skills.install(["claude-code"])
    assert not (canonical / "obsolete.md").exists()
    assert (home / ".claude/skills/icloud-agent/SKILL.md").read_bytes() == (
        canonical / "SKILL.md"
    ).read_bytes()


def test_migrates_owned_codex_copy_without_shadowing_shared_skill(home):
    legacy = owned(home / ".codex/skills/icloud-agent")
    agent_skills.install()
    assert not legacy.exists()
    assert (home / ".agents/skills/icloud-agent/SKILL.md").is_file()
    assert (home / ".codex/.icloud-agent-mcp").is_file()


def test_failed_commit_restores_every_previous_skill(home, monkeypatch):
    canonical = owned(home / ".agents/skills/icloud-agent", "previous shared skill")
    destination = owned(home / ".claude/skills/icloud-agent", "previous Claude skill")
    replace = Path.replace

    def fail_second_commit(self, target):
        if self.name == "new" and target == destination:
            raise OSError("disk failure")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_commit)
    with pytest.raises(OSError, match="disk failure"):
        agent_skills.install(["claude-code"])
    assert (canonical / "SKILL.md").read_text() == "previous shared skill"
    assert (destination / "SKILL.md").read_text() == "previous Claude skill"
    assert not destination.is_symlink()


def test_unknown_agent_cannot_create_a_path(home):
    with pytest.raises(AgentError, match="Unknown skill agent"):
        agent_skills.install(["../../elsewhere"])
    assert not list(home.iterdir())


def test_overlapping_agent_directory_is_rejected_without_writes(home, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".agents/skills/icloud-agent"))
    with pytest.raises(AgentError, match="must not contain one another"):
        agent_skills.install(["claude-code"])
    assert not list(home.iterdir())


def test_finish_option_does_not_install(home, monkeypatch):
    monkeypatch.setattr(terminal, "pick_one", lambda *args: "finish")
    agent_skills.offer(Console(file=io.StringIO()))
    assert not list(home.iterdir())


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), EOFError(), AgentError("setup_conflict", "Synthetic conflict")]
)
def test_optional_install_failure_returns_without_undoing_login(home, monkeypatch, failure):
    monkeypatch.setattr(terminal, "pick_one", lambda *args: "install")

    def fail(*args):
        raise failure

    monkeypatch.setattr(agent_skills, "choose_agents", fail)
    output = io.StringIO()
    agent_skills.offer(Console(file=output, theme=terminal.THEME))
    assert (
        "skipped" in output.getvalue() or "Retry: icloud-agent setup --skills" in output.getvalue()
    )
    assert not list(home.iterdir())
