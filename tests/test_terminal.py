import io
import json
import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from rich.console import Console

from icloud_agent import auth, cli, terminal
from icloud_agent.errors import AgentError


class TerminalStream(io.StringIO):
    def isatty(self):
        return True


def run_cli(monkeypatch, args, *, tty=False):
    stdout = TerminalStream() if tty else io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["icloud-agent", *args])
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    code = 0
    try:
        cli.main()
    except SystemExit as exc:
        code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ["--json", "mail", "search", "--dry-run"],
        ["mail", "--json", "search", "--dry-run"],
        ["mail", "search", "--json", "--dry-run"],
    ],
)
def test_explicit_json_in_tty(monkeypatch, args):
    code, stdout, stderr = run_cli(monkeypatch, args, tty=True)
    assert code == 0 and not stderr
    assert json.loads(stdout)["data"]["executed"] is False
    assert "\x1b" not in stdout


def test_piped_output_is_automatically_json(monkeypatch):
    code, stdout, stderr = run_cli(monkeypatch, ["mail", "folders", "--dry-run"])
    assert code == 0 and not stderr
    assert json.loads(stdout)["ok"]


def test_human_output_and_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    code, stdout, stderr = run_cli(monkeypatch, ["mail", "folders", "--dry-run"], tty=True)
    assert code == 0 and not stderr
    assert "icloud-agent" in stdout and "Executed" in stdout
    assert "\x1b" not in stdout


@pytest.mark.parametrize("tty, force_json", [(False, False), (True, True), (True, False)])
def test_errors_preserve_exit_codes_and_output_contract(monkeypatch, tmp_path, tty, force_json):
    monkeypatch.setattr(auth, "config_path", lambda: tmp_path / "missing.json")
    args = ["auth", "status"] + (["--json"] if force_json else [])
    code, stdout, stderr = run_cli(monkeypatch, args, tty=tty)
    assert code == 1
    if force_json or not tty:
        assert json.loads(stdout)["error"]["code"] == "not_authenticated"
        assert not stderr
    else:
        assert not stdout and "Not authenticated" in stderr


def test_usage_error_is_json_and_exit_two(monkeypatch):
    code, stdout, stderr = run_cli(monkeypatch, ["--json", "mail", "search", "--unknown"], tty=True)
    assert code == 2 and not stderr
    assert json.loads(stdout)["error"]["code"] == "invalid_arguments"


def test_bare_command_is_help_and_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    code, stdout, stderr = run_cli(monkeypatch, [], tty=True)
    assert code == 0 and not stderr
    assert "Get started: icloud-agent auth login" in stdout
    assert "\x1b" not in stdout


def test_external_content_is_literal_and_cannot_control_terminal():
    output = io.StringIO()
    out = Console(file=output, no_color=True, width=60, theme=terminal.THEME)
    malicious = "[bold red]hello[/bold red]\x1b[2J\x07\u202esecret"
    terminal.result(
        out, {"ok": True, "data": {"subject": malicious}}, SimpleNamespace(command="mail")
    )
    rendered = output.getvalue()
    assert "[bold red]hello[/bold red]" in rendered
    assert "\x1b" not in rendered and "\x07" not in rendered and "\u202e" not in rendered
    assert terminal.literal("Café ☁\nsecond\tcolumn") == "Café ☁\nsecond\tcolumn"


def mock_login(monkeypatch):
    monkeypatch.setattr(sys, "stdin", TerminalStream())
    entries = iter(["invalid", "person@icloud.com", "", ""])
    monkeypatch.setattr("builtins.input", lambda: next(entries))
    passwords = iter(["ordinary-password", "abcd-efgh-ijkl-mnop"])
    monkeypatch.setattr("getpass.getpass", lambda *a, **kw: next(passwords))
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(cli, "check_account", lambda account: [])
    monkeypatch.setattr(terminal, "choose", lambda out, title, choices, selected: selected)
    monkeypatch.setattr(terminal, "pick_one", lambda out, title, choices, selected: selected)
    saved = []
    monkeypatch.setattr(auth, "save", saved.append)
    return saved


def test_login_keeps_prompts_on_stderr_and_secret_out_of_output(monkeypatch):
    saved = mock_login(monkeypatch)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login", "--no-browser"])
    assert code == 0
    assert json.loads(stdout)["data"]["mail_address"] == "person@icloud.com"
    assert "Your account" in stderr and "Enter a valid email address" in stderr
    assert "iCloud Login Email Address" in stderr
    assert "Primary iCloud Mail Address" in stderr
    assert "xxxx-xxxx-xxxx-xxxx" in stderr
    assert "abcd-efgh-ijkl-mnop" not in stdout + stderr
    assert "ordinary-password" not in stdout + stderr
    assert len(saved) == 1 and saved[0].password == "abcd-efgh-ijkl-mnop"


def test_login_verification_failure_does_not_save(monkeypatch):
    saved = mock_login(monkeypatch)

    def fail(account):
        raise AgentError("test_failure", "Synthetic failed check")

    monkeypatch.setattr(cli, "check_account", fail)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login", "--no-browser"])
    assert code == 1 and not saved
    assert json.loads(stdout)["error"]["code"] == "test_failure"
    assert "abcd-efgh-ijkl-mnop" not in stdout + stderr


def test_closed_login_input_is_safe(monkeypatch):
    mock_login(monkeypatch)

    def close():
        raise EOFError

    monkeypatch.setattr("builtins.input", close)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login", "--no-browser"])
    assert code == 1
    assert json.loads(stdout)["error"]["code"] == "cancelled"


def test_login_rejects_piped_credentials(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not a credential channel"))
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login", "--no-browser"])
    assert code == 1 and not stderr
    assert json.loads(stdout)["error"]["code"] == "interactive_login_required"
