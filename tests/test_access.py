import io
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input

from icloud_agent import auth, calendar, cli, discovery, mail, operations, terminal
from icloud_agent.errors import AgentError

CALENDAR = "https://p01-caldav.icloud.com/123/home/"


def account():
    return auth.Account(
        "apple@example.com",
        "mail@icloud.com",
        "test-secret",
        ["alias@icloud.com"],
        [CALENDAR],
        ["mail@icloud.com", "alias@icloud.com"],
        "alias@icloud.com",
    )


@pytest.mark.parametrize(
    "operation,values",
    [
        ("calendar_search", {"calendar_id": CALENDAR, "start": "2026-10-01", "end": "2026-10-02"}),
        (
            "calendar_create",
            {"calendar_id": CALENDAR, "title": "Test", "start": "2026-10-01", "end": "2026-10-02"},
        ),
        ("calendar_read", {"event_id": calendar.event_id(CALENDAR, CALENDAR + "event.ics")}),
        (
            "calendar_update",
            {
                "event_id": calendar.event_id(CALENDAR, CALENDAR + "event.ics"),
                "etag": "x",
                "title": "Updated",
            },
        ),
        (
            "calendar_delete",
            {"event_id": calendar.event_id(CALENDAR, CALENDAR + "event.ics"), "etag": "x"},
        ),
    ],
)
def test_disabled_calendar_is_denied_before_transport(monkeypatch, operation, values):
    selected = account()
    selected.calendar_ids = []
    monkeypatch.setattr(auth, "load", lambda: selected)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(calendar, "connection", lambda a: pytest.fail("Calendar network access"))
    result = operations.invoke(operation, values)
    assert result["error"]["code"] == "calendar_disabled"


def test_calendar_list_filters_new_and_disabled_resources(monkeypatch):
    selected = account()
    found = [{"id": CALENDAR, "name": "Home"}, {"id": CALENDAR + "other/", "name": "New"}]
    monkeypatch.setattr(calendar, "discover", lambda a: found)
    assert calendar.calendars(selected) == found[:1]
    selected.calendar_ids = []
    assert calendar.calendars(selected) == []


def test_sender_selection_has_no_unrestricted_fallback():
    selected = account()
    assert mail.enabled_sender(selected, None) == "alias@icloud.com"
    assert mail.enabled_sender(selected, "ALIAS@icloud.com") == "ALIAS@icloud.com"
    with pytest.raises(AgentError, match="not enabled"):
        mail.enabled_sender(selected, "mail@icloud.com")
    selected.sender_addresses = []
    with pytest.raises(AgentError, match="not enabled"):
        mail.enabled_sender(selected, None)


def test_disabled_draft_sender_is_rejected_before_network(monkeypatch):
    monkeypatch.setattr(mail, "connection", lambda a: pytest.fail("Mail network access"))
    with pytest.raises(AgentError, match="not enabled"):
        mail.draft(account(), ["to@example.com"], "Test", "Body", from_address="mail@icloud.com")


def test_enabled_sender_is_discoverable_to_agents(monkeypatch):
    monkeypatch.setattr(auth, "load", account)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    result = operations.invoke("mail_senders", {})
    assert result["data"] == {"addresses": ["alias@icloud.com"], "default": "alias@icloud.com"}


def test_old_config_requires_explicit_access_selection(monkeypatch, tmp_path):
    path = tmp_path / "account.json"
    path.write_text('{"apple_account":"apple@example.com","mail_address":"mail@icloud.com"}')
    monkeypatch.setattr(auth, "config_path", lambda: path)
    monkeypatch.setattr(auth, "credential_store", lambda: pytest.fail("Keychain read"))
    with pytest.raises(AgentError, match="choose access"):
        auth.load()


def test_picker_handles_space_arrows_enter_without_stdout(capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    out = SimpleNamespace(file=io.StringIO())
    with create_pipe_input() as pipe, create_app_session(input=pipe):
        pipe.send_text(" \x1b[B \r")
        result = terminal.choose(out, "Enabled", [("One", "1"), ("Two", "2")], [])
    assert result == ["1", "2"]
    assert capsys.readouterr().out == ""


def test_picker_control_c_cancels():
    out = SimpleNamespace(file=io.StringIO())
    with create_pipe_input() as pipe, create_app_session(input=pipe):
        pipe.send_text("\x03")
        with pytest.raises(KeyboardInterrupt):
            terminal.choose(out, "Enabled", [("One", "1")], [])


def test_default_sender_picker_handles_arrows_and_enter(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    out = SimpleNamespace(file=io.StringIO())
    with create_pipe_input() as pipe, create_app_session(input=pipe):
        pipe.send_text("\x1b[B\r")
        result = terminal.pick_one(
            out,
            "Default Sender Address",
            [("Primary", "primary@icloud.com"), ("Alias", "alias@icloud.com")],
            "primary@icloud.com",
        )
    assert result == "alias@icloud.com"


def test_configure_cancel_preserves_saved_settings(monkeypatch, tmp_path):
    path = tmp_path / "account.json"
    path.write_text("original settings")
    monkeypatch.setattr(auth, "config_path", lambda: path)
    monkeypatch.setattr(auth, "load", account)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(auth, "save", lambda a: pytest.fail("Unexpected save"))
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(discovery, "account_resources", lambda a: {})

    def cancel(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "select_access", cancel)
    with pytest.raises(KeyboardInterrupt):
        cli.configure()
    assert path.read_text() == "original settings"


def test_configure_refuses_concurrent_replacement(monkeypatch, tmp_path):
    path = tmp_path / "account.json"
    path.write_text("original settings")
    monkeypatch.setattr(auth, "config_path", lambda: path)
    monkeypatch.setattr(auth, "load", account)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(auth, "save", lambda a: pytest.fail("Unexpected save"))
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(discovery, "account_resources", lambda a: {})
    monkeypatch.setattr(cli, "select_access", lambda *args: path.write_text("replaced settings"))
    with pytest.raises(AgentError, match="settings changed"):
        cli.configure()
    assert path.read_text() == "replaced settings"
