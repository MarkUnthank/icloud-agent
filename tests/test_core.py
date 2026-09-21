import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from types import SimpleNamespace

import pytest
from icalendar import Calendar, Event

from icloud_agent import auth, calendar, mail, operations
from icloud_agent.errors import AgentError

ACCOUNT = auth.Account("apple@example.com", "mail@icloud.com", "test-secret")
CALENDAR = "https://p01-caldav.icloud.com/123/home/"
EVENT_URL = CALENDAR + "event.ics"


@contextmanager
def yields(value):
    yield value


class FakeKeychain:
    def __init__(self):
        self.values = {}

    def get_password(self, service, user):
        return self.values.get((service, user))

    def set_password(self, service, user, password):
        self.values[service, user] = password

    def delete_password(self, service, user):
        del self.values[service, user]


def test_credentials_persist_outside_config_and_logout(monkeypatch, tmp_path):
    keychain = FakeKeychain()
    config = tmp_path / "config/account.json"
    monkeypatch.setattr(auth, "config_path", lambda: config)
    monkeypatch.setattr(auth, "credential_store", lambda: keychain)
    auth.save(ACCOUNT)
    assert "test-secret" not in config.read_text()
    assert "test-secret" not in repr(ACCOUNT)
    assert config.stat().st_mode & 0o777 == 0o600
    assert auth.load().password == "test-secret"
    auth.logout()
    assert not config.exists()
    assert not keychain.values


def test_missing_auth_does_not_touch_keychain(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(auth, "credential_store", lambda: pytest.fail("Unexpected credential read"))
    with pytest.raises(AgentError, match="auth login"):
        auth.load()


def test_switch_account_removes_old_credential(monkeypatch, tmp_path):
    keychain = FakeKeychain()
    monkeypatch.setattr(auth, "config_path", lambda: tmp_path / "account.json")
    monkeypatch.setattr(auth, "credential_store", lambda: keychain)
    auth.save(ACCOUNT)
    second = auth.Account("second@example.com", "second@icloud.com", "other-secret")
    auth.save(second)
    assert keychain.get_password(auth.SERVICE, ACCOUNT.apple_account) is None
    assert auth.load().apple_account == second.apple_account


def test_caldav_redirect_cannot_forward_credentials_to_external_host(monkeypatch):
    import niquests

    calls = []

    def request(self, method, url, **kwargs):
        calls.append(url)
        assert kwargs["allow_redirects"] is False
        return SimpleNamespace(status_code=302, headers={"Location": "https://evil.test/"})

    monkeypatch.setattr(niquests.Session, "request", request)
    with calendar.connection(ACCOUNT) as client:
        with pytest.raises(AgentError, match="icloud.com"):
            client.request("https://caldav.icloud.com/")
    assert calls == ["https://caldav.icloud.com/"]


def test_dry_run_never_loads_auth(monkeypatch):
    monkeypatch.setattr(auth, "load", lambda: pytest.fail("Unexpected credential read"))
    result = operations.invoke(
        "mail_draft", {"to": ["a@example.com"], "subject": "Hi", "body": "Hi"}, True
    )
    assert result["ok"] and result["data"]["executed"] is False
    invalid = operations.invoke("mail_send_draft", {"password": "secret"}, True)
    assert not invalid["ok"] and "secret" not in json.dumps(invalid)


def test_exceptions_do_not_leak_protocol_secrets(monkeypatch):
    monkeypatch.setattr(
        auth, "load", lambda: (_ for _ in ()).throw(RuntimeError("password=secret"))
    )
    result = operations.invoke("mail_folders", {})
    assert not result["ok"]
    assert "secret" not in json.dumps(result)


def test_stale_mail_ref_is_rejected():
    c = SimpleNamespace(select_folder=lambda *a, **k: {b"UIDVALIDITY": 99})
    with pytest.raises(AgentError, match="IDs changed"):
        mail.select_ref(c, mail.encode_ref("INBOX", 98, 1))


@pytest.mark.parametrize("value", ["garbage", "W10=", mail.encode_ref("INBOX", 1, -1)])
def test_bad_refs(value):
    with pytest.raises(AgentError):
        mail.decode_ref(value)


@pytest.mark.parametrize(
    "value", ["bad", "a@example.com\r\nBcc: b@example.com", "a@example.com,b@example.com"]
)
def test_recipient_validation(value):
    with pytest.raises(AgentError):
        mail.recipients([value])


def test_read_uses_peek_and_does_not_mark_seen(monkeypatch):
    msg = EmailMessage()
    msg["Subject"] = "Café"
    msg.set_content("Private body")
    calls = []

    def fetch(ids, fields):
        calls.append(fields)
        return {7: {b"RFC822.SIZE": len(msg.as_bytes()), b"BODY[]": msg.as_bytes()}}

    c = SimpleNamespace(select_folder=lambda *a, **kw: {b"UIDVALIDITY": 8}, fetch=fetch)
    monkeypatch.setattr(mail, "connection", lambda a: yields(c))
    result = mail.read(ACCOUNT, mail.encode_ref("INBOX", 8, 7))
    assert result["subject"] == "Café"
    assert result["body"] == "Private body\n"
    assert calls == [["RFC822.SIZE"], ["BODY.PEEK[]"]]


class DraftMailbox:
    def __init__(self):
        msg = EmailMessage(policy=policy.SMTP)
        msg["From"] = ACCOUNT.mail_address
        msg["To"] = "recipient@example.com"
        msg["Message-ID"] = "<test@example.com>"
        msg["Subject"] = "Test"
        msg.set_content("Body")
        self.raw = msg.as_bytes()
        self.appended = []
        self.expunged = []

    def list_folders(self):
        return [([b"\\Drafts"], b"/", "Drafts"), ([b"\\Sent"], b"/", "Sent")]

    def select_folder(self, *a, **kw):
        return {b"UIDVALIDITY": 1}

    def fetch(self, ids, fields):
        return {1: {b"RFC822.SIZE": len(self.raw), b"BODY[]": self.raw}}

    def append(self, *args, **kwargs):
        self.appended.append((args, kwargs))
        return b"[APPENDUID 1 2] appended"

    def has_capability(self, cap):
        return cap == "UIDPLUS"

    def delete_messages(self, ids):
        assert ids == [1]

    def expunge(self, ids):
        self.expunged.extend(ids)


class SMTP:
    sent = 0
    failure = False

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def ehlo(self):
        pass

    def starttls(self, **kwargs):
        assert "context" in kwargs

    def login(self, user, password):
        assert user == ACCOUNT.mail_address

    def send_message(self, *args, **kwargs):
        type(self).sent += 1
        if self.failure:
            raise OSError("a transport failure with private info")
        return {}


@pytest.fixture
def draft_transport(monkeypatch):
    mailbox = DraftMailbox()
    SMTP.sent = 0
    SMTP.failure = False
    monkeypatch.setattr(mail, "connection", lambda a: yields(mailbox))
    monkeypatch.setattr(mail.smtplib, "SMTP", SMTP)
    return mailbox, mail.encode_ref("Drafts", 1, 1), hashlib.sha256(mailbox.raw).hexdigest()


def test_send_changed_draft_never_contacts_smtp(draft_transport, tmp_path):
    mailbox, ref, digest = draft_transport
    mailbox.raw += b"changed"
    with pytest.raises(AgentError, match="changed"):
        mail.send_draft(ACCOUNT, ref, digest, tmp_path)
    assert SMTP.sent == 0


def test_send_once_and_only_uid_expunge(draft_transport, tmp_path):
    mailbox, ref, digest = draft_transport
    result = mail.send_draft(ACCOUNT, ref, digest, tmp_path)
    assert result["smtp_accepted"] and not result["delivery_confirmed"]
    assert mailbox.expunged == [1]
    with pytest.raises(AgentError, match="already had"):
        mail.send_draft(ACCOUNT, ref, digest, tmp_path)
    assert SMTP.sent == 1


def test_uncertain_send_is_not_retried(draft_transport, tmp_path):
    _, ref, digest = draft_transport
    SMTP.failure = True
    with pytest.raises(AgentError, match="may have occurred"):
        mail.send_draft(ACCOUNT, ref, digest, tmp_path)
    with pytest.raises(AgentError, match="already had"):
        mail.send_draft(ACCOUNT, ref, digest, tmp_path)
    assert SMTP.sent == 1


def test_calendar_time_rules():
    with pytest.raises(AgentError):
        calendar.parse_time("2026-09-22T10:00:00")
    with pytest.raises(AgentError):
        calendar.validate_range(
            calendar.parse_time("2026-09-22"), calendar.parse_time("2026-09-22")
        )
    assert calendar.parse_time("2026-09-22T10:00:00+02:00").utcoffset().total_seconds() == 7200


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/event",
        "http://caldav.icloud.com/x",
        "https://icloud.com.evil.test/x",
        "https://user:pw@icloud.com/x",
        "https://icloud.com:444/x",
    ],
)
def test_calendar_rejects_untrusted_urls(url):
    with pytest.raises(AgentError):
        calendar.trusted_url(url)


class CalendarClient:
    def __init__(self):
        doc = Calendar()
        doc.add("VERSION", "2.0")
        doc.add("PRODID", "-//test//EN")
        ev = Event()
        ev.add("UID", "example")
        ev.add("SUMMARY", "Before")
        ev.add("DTSTART", datetime(2026, 9, 22, 10, tzinfo=UTC))
        ev.add("DTEND", datetime(2026, 9, 22, 11, tzinfo=UTC))
        ev.add("X-APPLE-CUSTOM", "preserved")
        doc.add_component(ev)
        self.doc = doc
        self.writes = []
        self.etag = '"first"'
        self.write_status = 204

    def principal(self):
        return SimpleNamespace(calendars=lambda: [SimpleNamespace(url=CALENDAR, name="Home")])

    def request(self, url, method="GET", **kwargs):
        if method != "GET":
            self.writes.append((method, kwargs))
            return SimpleNamespace(status=self.write_status)
        return SimpleNamespace(status=200, raw=self.doc.to_ical(), headers={"Etag": self.etag})

    def put(self, url, data, headers):
        self.writes.append((url, headers))
        if self.write_status == 204:
            self.doc = Calendar.from_ical(data)
            self.etag = '"second"'
        return SimpleNamespace(status=self.write_status)


@pytest.fixture
def calendar_transport(monkeypatch):
    client = CalendarClient()
    monkeypatch.setattr(calendar, "connection", lambda a: yields(client))
    return client, calendar.event_id(CALENDAR, EVENT_URL)


def test_stale_etag_never_writes(calendar_transport):
    client, ref = calendar_transport
    with pytest.raises(AgentError, match="changed"):
        calendar.update(ACCOUNT, ref, '"old"', title="After")
    assert not client.writes


def test_calendar_preserves_unknown_fields_and_uses_conditional_put(calendar_transport):
    client, ref = calendar_transport
    result = calendar.update(ACCOUNT, ref, '"first"', title="After")
    assert client.writes[0][1]["If-Match"] == '"first"'
    assert str(client.doc.walk("VEVENT")[0]["X-APPLE-CUSTOM"]) == "preserved"
    assert result["events"][0]["title"] == "After"
    assert result["etag"] == '"second"' and result["verified"]


def test_calendar_concurrent_write_rejected(calendar_transport):
    client, ref = calendar_transport
    client.write_status = 412
    with pytest.raises(AgentError, match="another client"):
        calendar.update(ACCOUNT, ref, '"first"', title="After")
    assert str(client.doc.walk("VEVENT")[0]["SUMMARY"]) == "Before"


def test_recurring_edit_rejected_and_delete_needs_scope(calendar_transport):
    client, ref = calendar_transport
    client.doc.walk("VEVENT")[0].add("RRULE", {"FREQ": "DAILY"})
    with pytest.raises(AgentError, match="standalone"):
        calendar.update(ACCOUNT, ref, '"first"', title="After")
    with pytest.raises(AgentError, match="entire recurring series"):
        calendar.delete(ACCOUNT, ref, '"first"')
    assert not client.writes


def test_meeting_delete_rejected(calendar_transport):
    client, ref = calendar_transport
    client.doc.walk("VEVENT")[0].add("ATTENDEE", "mailto:someone@example.com")
    with pytest.raises(AgentError, match="attendees"):
        calendar.delete(ACCOUNT, ref, '"first"', whole_series=True)
    assert not client.writes


def test_cannot_escape_calendar_resource(calendar_transport):
    client, _ = calendar_transport
    for url in (
        CALENDAR + "../private.ics",
        CALENDAR + "%2e%2e/private.ics",
        CALENDAR + "sub/event.ics",
    ):
        with pytest.raises(AgentError, match="event ID"):
            calendar.resolve_event(client, calendar.event_id(CALENDAR, url))


def test_mcp_schemas_and_safe_dry_call():
    import asyncio

    from icloud_agent.mcp_server import build_server

    async def check():
        server = build_server()
        tools = await server.list_tools()
        assert len(tools) == len(operations.OPERATIONS) == 13
        by_name = {x.name: x for x in tools}
        assert by_name["mail_read"].annotations.readOnlyHint
        assert not by_name["mail_send_draft"].annotations.readOnlyHint
        assert by_name["calendar_delete"].annotations.destructiveHint
        assert "arguments" in by_name["mail_send_draft"].inputSchema["properties"]

    asyncio.run(check())
