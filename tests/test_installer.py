import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


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
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if command[:3] == ["codex", "mcp", "get"] else 0)

    def create(path, **kwargs):
        (path / "bin").mkdir(parents=True)
        (path / "bin/icloud-agent").touch()

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer.venv, "create", create)
    installer.main()
    base = tmp_path / "Library/Application Support/icloud-agent"
    executable = base / "runtime/bin/icloud-agent"
    assert ["codex", "mcp", "add", "icloud-agent", "--", str(executable), "mcp"] in calls
    config = json.loads((base / "plugin/icloud-agent/.mcp.json").read_text())
    assert config["mcpServers"]["icloud-agent"]["command"] == str(executable)
    assert (tmp_path / ".codex/skills/icloud-agent/SKILL.md").is_file()
    assert (tmp_path / ".local/bin/icloud-agent").resolve() == executable
