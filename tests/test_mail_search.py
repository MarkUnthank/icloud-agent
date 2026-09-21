import json
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone

import pytest
from filelock import FileLock
from imapclient import IMAPClient
from imapclient.exceptions import LoginError
from niquests.exceptions import Timeout as RequestTimeout

from icloud_agent import auth, mail, operations
from icloud_agent.errors import error_result

ACCOUNT = auth.Account("person@icloud.com", "person@icloud.com", "synthetic-secret")


class Mailbox:
    def __init__(self):
        self.criteria = []
        self.fetches = []

    def select_folder(self, folder, readonly):
        assert folder == "INBOX" and readonly is True
        return {b"UIDVALIDITY": 42}

    def search(self, criteria, charset):
        assert charset == "UTF-8"
        self.criteria.append(criteria)
        return [3, 8, 11]

    def fetch(self, ids, fields):
        self.fetches.append((ids, fields))
        return {
            uid: {
                b"BODY[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)]": (
                    b"From: Morgan <morgan@example.com>\r\n"
                    b"Subject: Invoice\r\nDate: 19 Sep 2026 11:00:00 +0200\r\n\r\n"
                ),
                b"FLAGS": [],
                b"RFC822.SIZE": 123,
                b"INTERNALDATE": datetime(2026, 9, 21, 9, tzinfo=timezone(timedelta(hours=2))),
            }
            for uid in ids
        }


@pytest.fixture
def mailbox(monkeypatch):
    client = Mailbox()
    monkeypatch.setattr(mail, "connection", lambda account: nullcontext(client))
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(auth, "load", lambda: ACCOUNT)
    return client


def test_unread_day_sender_and_subject_are_separate_imap_filters(mailbox):
    arguments = {
        "query": "payment",
        "sender": "Morgan",
        "subject": "Invoice",
        "unread": True,
        "since": "2026-09-21",
        "before": "2026-09-22",
        "limit": 2,
    }
    result = operations.invoke("mail_search", arguments)
    assert result["ok"]
    assert mailbox.criteria == [
        [
            "UNSEEN",
            "TEXT",
            "payment",
            "FROM",
            "Morgan",
            "SUBJECT",
            "Invoice",
            "SINCE",
            date(2026, 9, 21),
            "BEFORE",
            date(2026, 9, 22),
        ]
    ]
    page = result["data"]
    assert page["order"] == "uid_desc"
    assert [message["uid"] for message in page["messages"]] == [11, 8]
    assert page["next_before_uid"] == 8
    assert page["messages"][0]["internal_date"] == "2026-09-21T09:00:00+02:00"
    assert page["messages"][0]["date"] != page["messages"][0]["internal_date"]
    assert mail.decode_ref(page["messages"][0]["id"]) == ("INBOX", 42, 11)
    assert mailbox.fetches[0][0] == [11, 8]
    assert "BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)]" in mailbox.fetches[0][1]
    assert "INTERNALDATE" in mailbox.fetches[0][1]
    operations.invoke("mail_search", {**arguments, "before_uid": page["next_before_uid"]})
    assert mailbox.criteria[1] == mailbox.criteria[0] + ["UID", "1:7"]


@pytest.mark.parametrize(
    "query", ['FROM "Morgan"', 'TEXT "Casey Example"', "SINCE 21-Sep-2026 BEFORE 22-Sep-2026"]
)
def test_query_remains_literal_and_never_executes_embedded_search_syntax(mailbox, query):
    mail.search(ACCOUNT, query=query)
    assert mailbox.criteria == [["ALL", "TEXT", query]]


def test_sender_search_does_not_search_message_body(mailbox):
    mail.search(ACCOUNT, sender="Morgan")
    assert mailbox.criteria == [["ALL", "FROM", "Morgan"]]


def test_imapclient_serializes_filters_without_nested_syntax(mailbox, monkeypatch):
    wire = []
    client = object.__new__(IMAPClient)
    client._raw_command_untagged = lambda command, arguments: (
        wire.append((command, arguments)) or [b""]
    )
    monkeypatch.setattr(mailbox, "search", client.search)
    result = mail.search(ACCOUNT, sender='Morgan "Smith"', since="2026-09-21", before="2026-09-22")
    assert result["messages"] == []
    assert wire == [
        (
            b"SEARCH",
            [
                b"CHARSET",
                b"UTF-8",
                b"ALL",
                b"FROM",
                b'"Morgan \\"Smith\\""',
                b"SINCE",
                b"21-Sep-2026",
                b"BEFORE",
                b"22-Sep-2026",
            ],
        )
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        {"since": "21-Sep-2026"},
        {"since": "2026-02-30"},
        {"before": "2026-13-01"},
        {"since": "2026-09-21T00:00:00Z"},
        {"since": 20260921},
        {"since": "2026-09-21", "before": "2026-09-21"},
        {"since": "2026-09-22", "before": "2026-09-21"},
        {"sender": ""},
        {"subject": ""},
    ],
)
def test_invalid_filters_fail_before_credentials_or_network(monkeypatch, arguments):
    monkeypatch.setattr(auth, "load", lambda: pytest.fail("Unexpected credentials"))
    result = operations.invoke("mail_search", arguments)
    assert result["error"]["code"] == "invalid_arguments"


def test_exhausted_uid_page_does_not_issue_a_wrapping_uid_range(mailbox):
    result = mail.search(ACCOUNT, before_uid=1)
    assert result == {"messages": [], "next_before_uid": None, "order": "uid_desc"}
    assert not mailbox.criteria and not mailbox.fetches


@pytest.mark.parametrize(
    "method,stage",
    [("select_folder", "select_folder"), ("search", "search"), ("fetch", "fetch_headers")],
)
def test_imap_timeout_reports_safe_stage_and_never_empty_success(
    mailbox, monkeypatch, method, stage
):
    def timeout(*args, **kwargs):
        raise TimeoutError("private server response, subject, and credential")

    monkeypatch.setattr(mailbox, method, timeout)
    result = operations.invoke("mail_search", {"query": "private query"})
    error = result["error"]
    assert result["ok"] is False and "data" not in result
    assert error["code"] == "operation_timeout"
    assert error["operation"] == "mail_search"
    assert error["service"] == "imap" and error["stage"] == stage
    assert error["timeout_seconds"] == 30 and error["retryable"] is True
    if stage in ("search", "fetch_headers"):
        assert "Narrow the date range" in error["recovery"]
    else:
        assert "Check connectivity" in error["recovery"]
    assert "private" not in json.dumps(result)


def test_lock_contention_is_not_network_or_authentication_failure(monkeypatch, tmp_path):
    lock_path = tmp_path / "operations.lock"
    monkeypatch.setattr(auth, "operation_lock", lambda: FileLock(lock_path, timeout=0))
    monkeypatch.setattr(auth, "load", lambda: pytest.fail("Operation must not start"))
    with FileLock(lock_path):
        result = operations.invoke("mail_search", {})
    assert result["error"]["code"] == "operation_busy"
    assert result["error"]["stage"] == "lock"
    assert result["error"]["executed"] is False
    assert str(lock_path) not in json.dumps(result)


@pytest.mark.parametrize(
    "failure,code,stage",
    [
        (LoginError("secret protocol login response"), "authentication_failed", "authenticate"),
        (TimeoutError("secret timeout response"), "operation_timeout", "authenticate"),
    ],
)
def test_login_timeout_and_rejected_password_have_different_errors(
    monkeypatch, failure, code, stage
):
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            raise failure

    client = Client()
    monkeypatch.setattr(mail, "IMAPClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(auth, "load", lambda: ACCOUNT)
    result = operations.invoke("mail_search", {})
    assert result["error"]["code"] == code
    assert result["error"]["stage"] == stage
    assert client.normalise_times is False
    if code == "operation_timeout":
        assert "Check connectivity" in result["error"]["recovery"]
    assert "secret" not in json.dumps(result)


def test_network_timeout_during_a_write_requires_readback():
    result = error_result(RequestTimeout("private URL"), operation="calendar_create", write=True)
    assert result["error"]["code"] == "operation_timeout"
    assert result["error"]["retryable"] is False
    assert "Read back" in result["error"]["recovery"]
    assert "private" not in json.dumps(result)
