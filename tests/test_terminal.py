import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from rich.console import Console
from rich.text import Text

from icloud_agent import agent_skills, auth, cli, terminal
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


@pytest.mark.parametrize("force_json", [False, True])
def test_connected_card_keeps_login_success_and_json_contract(monkeypatch, force_json):
    monkeypatch.setenv("NO_COLOR", "")
    data = {"mail_address": "person@icloud.com"}
    monkeypatch.setattr(cli, "login", lambda no_browser: data)
    args = ["auth", "login"] + (["--json"] if force_json else [])
    code, stdout, stderr = run_cli(monkeypatch, args, tty=True)
    assert code == 0 and not stderr
    assert "\x1b" not in stdout
    if force_json:
        assert json.loads(stdout) == {"ok": True, "data": data}
    else:
        assert "✓  Connected to iCloud" in stdout
        assert "person@icloud.com" in stdout


@pytest.mark.parametrize(
    "tty,force_json,offered", [(True, False, True), (True, True, False), (False, False, False)]
)
def test_optional_skills_only_after_success_in_a_human_terminal(
    monkeypatch, tty, force_json, offered
):
    monkeypatch.setattr(sys, "stdin", TerminalStream())
    monkeypatch.setattr(cli, "login", lambda no_browser: {"mail_address": "person@icloud.com"})
    calls = []

    def offer(out):
        assert "Connected to iCloud" in sys.stdout.getvalue()
        calls.append(True)

    monkeypatch.setattr(agent_skills, "offer", offer)
    args = ["auth", "login"] + (["--json"] if force_json else [])
    code, stdout, stderr = run_cli(monkeypatch, args, tty=tty)
    assert code == 0 and bool(calls) is offered
    if not offered:
        assert json.loads(stdout)["ok"]


def test_optional_skill_failure_keeps_successful_login_exit_status(monkeypatch):
    monkeypatch.setattr(sys, "stdin", TerminalStream())
    monkeypatch.setattr(cli, "login", lambda no_browser: {"mail_address": "person@icloud.com"})
    monkeypatch.setattr(terminal, "pick_one", lambda *args: "install")
    monkeypatch.setattr(agent_skills, "choose_agents", lambda out: [])

    def fail(*args):
        raise AgentError("setup_conflict", "User-owned skill exists.")

    monkeypatch.setattr(agent_skills, "install", fail)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login"], tty=True)
    assert code == 0 and "Connected to iCloud" in stdout
    assert "Agent skills were not installed" in stderr
    assert "Retry: icloud-agent setup --skills" in stderr


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
    monkeypatch.setattr(
        cli.webbrowser, "open", lambda url: pytest.fail("Unexpected browser launch")
    )
    monkeypatch.setattr(sys, "stdin", TerminalStream())
    entries = iter(["invalid", "person@icloud.com", ""])
    monkeypatch.setattr("builtins.input", lambda: next(entries))
    passwords = iter(["ordinary-password", "abcd-efgh-ijkl-mnop"])

    def password_input(out, prompt):
        out.print(prompt)
        return next(passwords)

    monkeypatch.setattr(terminal, "password_input", password_input)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(
        cli,
        "check_account",
        lambda account: {"addresses": [], "display_name": "Alex Example", "calendars": []},
    )
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
    assert "Primary iCloud Mail Address" not in stderr
    assert "https://account.apple.com/sign-in" in stderr
    assert "[Press enter to open in browser]" not in stderr
    assert "xxxx-xxxx-xxxx-xxxx" in stderr
    assert "abcd-efgh-ijkl-mnop" not in stdout + stderr
    assert "ordinary-password" not in stdout + stderr
    assert len(saved) == 1 and saved[0].password == "abcd-efgh-ijkl-mnop"
    assert saved[0].apple_account == saved[0].mail_address == "person@icloud.com"
    assert "Sender name [Alex Example]" in stderr
    assert saved[0].sender_name == "Alex Example"


def test_login_waits_for_enter_before_opening_displayed_url(monkeypatch):
    saved = mock_login(monkeypatch)
    events = []
    entries = iter(["person@icloud.com", "", "Alex at Work"])

    def enter():
        events.append("input")
        return next(entries)

    def open_browser(url):
        assert events == ["input", "input"]
        events.append(url)
        return True

    monkeypatch.setattr("builtins.input", enter)
    monkeypatch.setattr(cli.webbrowser, "open", open_browser)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login"])
    assert code == 0 and json.loads(stdout)["ok"]
    assert events == ["input", "input", "https://account.apple.com/sign-in", "input"]
    assert saved[0].sender_name == "Alex at Work"
    assert (
        stderr.index("https://account.apple.com/sign-in")
        < stderr.index("[Press enter to open in browser]")
        < stderr.index("App-specific password ›")
    )


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_cancel_at_browser_prompt_never_opens_browser_or_saves(monkeypatch, interruption):
    saved = mock_login(monkeypatch)
    entries = iter(["person@icloud.com"])

    def enter():
        try:
            return next(entries)
        except StopIteration:
            raise interruption from None

    monkeypatch.setattr("builtins.input", enter)
    code, stdout, stderr = run_cli(monkeypatch, ["auth", "login"])
    assert code == 1 and not saved
    assert json.loads(stdout)["error"]["code"] == "cancelled"
    assert "[Press enter to open in browser]" in stderr
    assert "App-specific password ›" not in stderr


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


@pytest.mark.parametrize(
    "args,write_warning",
    [
        (["mail", "search"], False),
        (["mail", "draft"], True),
        (["mail", "draft", "--dry-run"], False),
    ],
)
def test_cancel_warning_only_for_executing_writes(monkeypatch, args, write_warning):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "invoke", interrupt)
    code, stdout, stderr = run_cli(monkeypatch, args, tty=True)
    assert code == 1 and not stdout
    assert stderr.count("Cancelled") == 1
    assert ("Check the result before retrying this write." in stderr) is write_warning


@pytest.mark.parametrize(
    "pasted",
    [
        "abcd-efgh-ijkl-mnop\n",
        "abcd-efgh-ijkl-mnop\r\n",
        "abcd-efgh-ijkl-mnop\r",
        " \tabcd-efgh-ijkl-mnop\n\n ",
        "abcd-efgh\n-ijkl-mnop",
    ],
)
def test_password_paste_is_masked_and_waits_for_enter(monkeypatch, capsys, pasted):
    monkeypatch.setenv("NO_COLOR", "1")
    ready, masked = Event(), Event()

    class Output(io.StringIO):
        def write(self, value):
            result = super().write(value)
            if "Password" in value:
                ready.set()
            if "*" in value:
                masked.set()
            return result

    output = Output()
    with create_pipe_input() as pipe, ThreadPoolExecutor(max_workers=1) as pool:

        def read_password():
            with create_app_session(input=pipe):
                return terminal.password_input(
                    SimpleNamespace(file=output), Text("  Password (hidden) › ")
                )

        pending = pool.submit(read_password)
        try:
            assert ready.wait(3), "Password prompt never rendered"
            pipe.send_text("\x1b[200~" + pasted + "\x1b[201~")
            assert masked.wait(3), "Pasted password was not rendered as masked input"
            with pytest.raises(TimeoutError):
                pending.result(timeout=0.1)
            pipe.send_text("\r")
            expected = pasted.strip()
            assert pending.result(timeout=3) == expected.replace("\r\n", "\n").replace("\r", "\n")
        finally:
            if not pending.done():
                pipe.send_text("\x03")
    assert "abcd" not in output.getvalue() and "mnop" not in output.getvalue()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("key,exception", [("\x03", KeyboardInterrupt), ("\x04", EOFError)])
def test_password_prompt_can_be_cancelled(key, exception):
    with create_pipe_input() as pipe, create_app_session(input=pipe):
        pipe.send_text(key)
        with pytest.raises(exception):
            terminal.password_input(SimpleNamespace(file=io.StringIO()), Text("Password › "))
