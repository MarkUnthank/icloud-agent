import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from icloud_agent import setup


def load_installer():
    location = Path(__file__).resolve().parents[1] / "install.py"
    spec = importlib.util.spec_from_file_location("installer", location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_registers_absolute_executable_and_skill(monkeypatch, tmp_path):
    installer = load_installer()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(installer.sys, "platform", "darwin")
    monkeypatch.setattr(installer.sys, "argv", ["install.py", "--codex"])
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/local/bin/codex")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    base = tmp_path / "Library/Application Support/icloud-agent"
    executable = base / "runtime/bin/icloud-agent"
    monkeypatch.setattr(setup, "user_data_path", lambda *a, **kw: base)
    monkeypatch.setattr(setup, "executable_path", lambda: executable)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command == [str(executable), "setup", "--codex"]:
            setup.setup(codex=True)
        return SimpleNamespace(returncode=1 if command[1:3] == ["mcp", "get"] else 0)

    def create(path, **kwargs):
        (path / "bin").mkdir(parents=True)
        (path / "bin/icloud-agent").touch()

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer.venv, "create", create)
    installer.main()
    assert [
        "/usr/local/bin/codex",
        "mcp",
        "add",
        "icloud-agent",
        "--",
        str(executable),
        "mcp",
    ] in calls
    config = json.loads((base / "plugin/icloud-agent/.mcp.json").read_text())
    assert config["mcpServers"]["icloud-agent"]["command"] == str(executable)
    assert (tmp_path / ".agents/skills/icloud-agent/SKILL.md").is_file()
    assert (tmp_path / ".local/bin/icloud-agent").resolve() == executable
