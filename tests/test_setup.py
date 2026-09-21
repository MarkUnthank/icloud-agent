import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from icloud_agent import setup
from icloud_agent.errors import AgentError


@pytest.fixture
def integration(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, "user_data_path", lambda *a, **k: tmp_path / "data")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom-codex"))
    monkeypatch.setattr(setup, "executable_path", lambda: Path("/opt/homebrew/bin/icloud-agent"))
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/bin/codex")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if "get" in command else 0)

    monkeypatch.setattr(setup.subprocess, "run", run)
    return tmp_path, calls


def test_setup_bundled_plugin_and_custom_codex_home(integration):
    root, calls = integration
    result = setup.setup(codex=True)
    plugin = Path(result["plugin"])
    config = json.loads((plugin / ".mcp.json").read_text())
    assert config["mcpServers"]["icloud-agent"]["command"] == "/opt/homebrew/bin/icloud-agent"
    assert (root / "custom-codex/skills/icloud-agent/SKILL.md").is_file()
    assert calls[-1] == [
        "/bin/codex",
        "mcp",
        "add",
        "icloud-agent",
        "--",
        "/opt/homebrew/bin/icloud-agent",
        "mcp",
    ]
    setup.setup(codex=True)  # Updating our own skill remains possible.


def test_setup_preserves_unmanaged_skill(integration):
    root, calls = integration
    skill = root / "custom-codex/skills/icloud-agent"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("user content")
    with pytest.raises(AgentError, match="unmanaged skill"):
        setup.setup(codex=True)
    assert (skill / "SKILL.md").read_text() == "user content"
    assert not calls
    assert not (root / "data").exists()


def test_setup_preserves_unmanaged_mcp(integration, monkeypatch):
    root, calls = integration
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    with pytest.raises(AgentError, match="unmanaged.*MCP"):
        setup.setup(codex=True)
    assert not (root / "data").exists()


def test_setup_without_codex(integration):
    root, calls = integration
    result = setup.setup()
    assert not result["codex_registered"]
    assert (Path(result["plugin"]) / "skills/icloud-agent/SKILL.md").is_file()
    assert not calls


def test_executable_keeps_stable_symlink(monkeypatch, tmp_path):
    target = tmp_path / "Cellar/0.2.0/icloud-agent"
    target.parent.mkdir(parents=True)
    target.touch()
    stable = tmp_path / "bin/icloud-agent"
    stable.parent.mkdir()
    stable.symlink_to(target)
    monkeypatch.setattr(setup.sys, "argv", [str(stable), "setup"])
    assert setup.executable_path() == stable
