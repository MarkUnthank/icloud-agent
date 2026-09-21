import copy
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import date
from threading import Event
from types import SimpleNamespace

import pytest
from icalendar import Calendar

from icloud_agent import auth, calendar, calendar_drafts, operations
from icloud_agent.errors import AgentError

CALENDAR = "https://p01-caldav.icloud.com/123/home/"
OTHER_CALENDAR = "https://p01-caldav.icloud.com/123/work/"
EVENT = {
    "calendar_id": CALENDAR,
    "title": "Lunch with Alex",
    "start": "2026-10-01T12:00:00+02:00",
    "end": "2026-10-01T13:00:00+02:00",
    "location": "Café",
    "description": "Bring the project notes.",
}


class Remote:
    def __init__(self):
        self.puts = []
        self.events = {}
        self.failure = None
        self.status = 201
        self.read_status = 200

    def principal(self):
        return SimpleNamespace(
            calendars=lambda: [
                SimpleNamespace(url=CALENDAR, name="Personal"),
                SimpleNamespace(url=OTHER_CALENDAR, name="Work"),
            ]
        )

    def put(self, url, data, headers):
        self.puts.append((url, data, headers))
        if self.status in (201, 204):
            self.events[url] = data.encode()
        if self.failure:
            raise self.failure
        return SimpleNamespace(status=self.status)

    def request(self, url):
        return SimpleNamespace(
            status=self.read_status if url in self.events else 404,
            raw=self.events.get(url, b""),
            headers={"Etag": '"created"'},
        )


@pytest.fixture
def env(monkeypatch, tmp_path):
    account = auth.Account(
        "alex@icloud.com",
        "alex@icloud.com",
        "private-password",
        calendar_ids=[CALENDAR, OTHER_CALENDAR],
    )
    remote = Remote()
    calls = []

    @contextmanager
    def connection(value):
        assert value is account
        calls.append(True)
        yield remote

    monkeypatch.setattr(calendar_drafts, "store_path", lambda: tmp_path / "state/drafts.sqlite3")
    monkeypatch.setattr(calendar, "connection", connection)
    monkeypatch.setattr(auth, "load", lambda: account)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    return SimpleNamespace(account=account, remote=remote, connections=calls, root=tmp_path)


def invoke(operation, **values):
    result = operations.invoke(operation, values)
    assert result["ok"], result
    return result["data"]


def reviewed(draft):
    return {"draft_id": draft["draft_id"], "expected_sha256": draft["sha256"]}


def test_draft_persists_complete_review_without_remote_writes(env):
    draft = invoke("calendar_draft", **EVENT)
    assert draft["status"] == "draft" and draft["revision"] == 1
    assert draft["event"] == {**EVENT, "calendar_name": "Personal", "all_day": False}
    assert invoke("calendar_read_draft", draft_id=draft["draft_id"]) == draft
    assert not env.remote.puts
    assert len(env.connections) == 1  # Only calendar discovery, not the local read.
    path = calendar_drafts.store_path()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert b"private-password" not in path.read_bytes()


def test_draft_listing_is_account_scoped_and_paginates(env):
    saved = [invoke("calendar_draft", **{**EVENT, "title": str(i)}) for i in range(3)]
    first = invoke("calendar_drafts", limit=2)
    assert [x["draft_id"] for x in first["drafts"]] == [x["draft_id"] for x in saved[:0:-1]]
    second = invoke("calendar_drafts", limit=2, before=first["next_before"])
    assert second["drafts"] == saved[:1] and second["next_before"] is None
    env.account.apple_account = "another@icloud.com"
    assert invoke("calendar_drafts")["drafts"] == []
    for name in (
        "calendar_read_draft",
        "calendar_update_draft",
        "calendar_discard_draft",
        "calendar_create",
    ):
        arguments = {"draft_id": saved[0]["draft_id"]}
        if name != "calendar_read_draft":
            arguments.update(reviewed(saved[0]))
        if name == "calendar_update_draft":
            arguments["title"] = "Other account"
        if name == "calendar_create":
            arguments["confirmed"] = True
        result = operations.invoke(name, arguments)
        assert result["error"]["code"] == "draft_not_found"
    assert not env.remote.puts


def test_revision_requires_fresh_review_even_when_restoring_original_content(env):
    original = invoke("calendar_draft", **EVENT)
    updated = invoke("calendar_update_draft", **reviewed(original), title="New lunch", location="")
    assert updated["sha256"] != original["sha256"] and updated["revision"] == 2
    assert updated["event"]["location"] == ""
    stale = operations.invoke("calendar_create", {**reviewed(original), "confirmed": True})
    assert stale["error"]["code"] == "draft_changed"
    restored = invoke(
        "calendar_update_draft",
        **reviewed(updated),
        title=EVENT["title"],
        location=EVENT["location"],
    )
    assert restored["event"] == original["event"]
    assert restored["sha256"] != original["sha256"]
    assert not env.remote.puts


def test_revising_destination_changes_preview_and_rejects_disabled_calendar(env):
    draft = invoke("calendar_draft", **EVENT)
    changed = invoke("calendar_update_draft", **reviewed(draft), calendar_id=OTHER_CALENDAR)
    assert changed["event"]["calendar_name"] == "Work"
    assert changed["event"]["calendar_id"] == OTHER_CALENDAR
    env.account.calendar_ids = [CALENDAR]
    result = operations.invoke("calendar_create", {**reviewed(changed), "confirmed": True})
    assert result["error"]["code"] == "calendar_disabled"
    assert not env.remote.puts
    # Discarding a local proposal remains possible after disabling its destination.
    assert invoke("calendar_discard_draft", **reviewed(changed))["discarded"]


def test_discard_requires_current_revision_and_never_contacts_apple(env):
    draft = invoke("calendar_draft", **EVENT)
    changed = invoke("calendar_update_draft", **reviewed(draft), title="Changed")
    stale = operations.invoke("calendar_discard_draft", reviewed(draft))
    assert stale["error"]["code"] == "draft_changed"
    calls = len(env.connections)
    assert invoke("calendar_discard_draft", **reviewed(changed))["discarded"]
    assert len(env.connections) == calls and not env.remote.puts
    assert (
        operations.invoke("calendar_read_draft", {"draft_id": draft["draft_id"]})["error"]["code"]
        == "draft_not_found"
    )


@pytest.mark.parametrize("confirmation", [None, False, "true", 1])
def test_creation_requires_explicit_strict_confirmation(env, confirmation):
    draft = invoke("calendar_draft", **EVENT)
    values = reviewed(draft)
    if confirmation is not None:
        values["confirmed"] = confirmation
    calls = len(env.connections)
    result = operations.invoke("calendar_create", values)
    assert result["error"]["code"] == "invalid_arguments"
    assert len(env.connections) == calls and not env.remote.puts


def test_direct_creation_schema_cannot_bypass_draft_review(env):
    result = operations.invoke("calendar_create", EVENT)
    assert result["error"]["code"] == "invalid_arguments"
    assert not env.remote.puts and not env.connections


@pytest.mark.parametrize("all_day", [False, True])
def test_confirm_creates_reviewed_event_once_with_conditional_put(env, all_day):
    event = {**EVENT, "start": "2026-10-01", "end": "2026-10-02"} if all_day else EVENT
    draft = invoke("calendar_draft", **event)
    result = invoke("calendar_create", **reviewed(draft), confirmed=True)
    assert result["created"] and result["verified"]
    url, data, headers = env.remote.puts[0]
    assert url == CALENDAR + draft["draft_id"] + ".ics"
    assert headers["If-None-Match"] == "*"
    component = Calendar.from_ical(data).walk("VEVENT")[0]
    assert str(component["UID"]) == draft["draft_id"]
    assert str(component["SUMMARY"]) == event["title"]
    assert str(component["DESCRIPTION"]) == event["description"]
    assert str(component["LOCATION"]) == event["location"]
    assert component["DTSTART"].dt == calendar.parse_time(event["start"])
    assert component["DTEND"].dt == calendar.parse_time(event["end"])
    assert (type(component["DTSTART"].dt) is date) is all_day
    assert "ATTENDEE" not in component and "RRULE" not in component
    repeated = invoke("calendar_create", **reviewed(draft), confirmed=True)
    assert repeated["already_created"] and repeated["id"] == result["id"]
    assert len(env.remote.puts) == 1
    saved = invoke("calendar_read_draft", draft_id=draft["draft_id"])
    assert saved["status"] == "created" and saved["event_id"] == result["id"]
    assert saved["creation"] == result
    for operation, changes in (
        ("calendar_discard_draft", {}),
        ("calendar_update_draft", {"title": "Again"}),
    ):
        assert (
            operations.invoke(operation, {**reviewed(draft), **changes})["error"]["code"]
            == "draft_locked"
        )


@pytest.mark.parametrize(
    "failure", [TimeoutError("private response"), ConnectionError("private response")]
)
def test_uncertain_creation_keeps_stable_id_and_blocks_further_attempts(env, failure):
    draft = invoke("calendar_draft", **EVENT)
    env.remote.failure = failure
    for _ in range(2):
        result = operations.invoke("calendar_create", {**reviewed(draft), "confirmed": True})
        assert result["error"]["code"] == "calendar_create_unconfirmed"
        assert result["error"]["retryable"] is False
        assert "private response" not in json.dumps(result)
    assert len(env.remote.puts) == 1
    saved = invoke("calendar_read_draft", draft_id=draft["draft_id"])
    assert saved["status"] == "attempted" and saved["event_id"] == result["error"]["event_id"]
    readback = invoke("calendar_read", event_id=saved["event_id"])
    assert readback["events"][0]["title"] == EVENT["title"]
    assert (
        operations.invoke("calendar_discard_draft", reviewed(draft))["error"]["code"]
        == "draft_locked"
    )


def test_interruption_after_put_keeps_attempt_record(env):
    draft = invoke("calendar_draft", **EVENT)
    env.remote.failure = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        calendar_drafts.create(env.account, **reviewed(draft), confirmed=True)
    assert invoke("calendar_read_draft", draft_id=draft["draft_id"])["status"] == "attempted"
    result = operations.invoke("calendar_create", {**reviewed(draft), "confirmed": True})
    assert result["error"]["code"] == "calendar_create_unconfirmed"
    assert len(env.remote.puts) == 1


@pytest.mark.parametrize("status", [403, 412, 500])
def test_http_failure_retains_attempt_without_overwriting_or_retrying(env, status):
    draft = invoke("calendar_draft", **EVENT)
    env.remote.status = status
    result = operations.invoke("calendar_create", {**reviewed(draft), "confirmed": True})
    assert result["error"]["code"] == "calendar_create_unconfirmed"
    assert not env.remote.events
    assert invoke("calendar_read_draft", draft_id=draft["draft_id"])["status"] == "attempted"


def test_failed_readback_does_not_turn_success_into_a_second_create(env):
    draft = invoke("calendar_draft", **EVENT)
    env.remote.read_status = 500
    result = invoke("calendar_create", **reviewed(draft), confirmed=True)
    assert result["created"] and not result["verified"]
    assert invoke("calendar_create", **reviewed(draft), confirmed=True)["already_created"]
    assert len(env.remote.puts) == 1


def test_failed_preflight_keeps_draft_editable(env, monkeypatch):
    draft = invoke("calendar_draft", **EVENT)

    def fail(*args):
        raise ConnectionError("private URL")

    monkeypatch.setattr(calendar, "connection", fail)
    result = operations.invoke("calendar_create", {**reviewed(draft), "confirmed": True})
    assert not result["ok"] and "private URL" not in json.dumps(result)
    assert invoke("calendar_read_draft", draft_id=draft["draft_id"])["status"] == "draft"
    assert (
        invoke("calendar_update_draft", **reviewed(draft), title="Still editable")["revision"] == 2
    )
    assert not env.remote.puts


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-10-01T12:00:00", "2026-10-01T13:00:00"),
        ("2026-10-02", "2026-10-01"),
        ("2026-10-01", "2026-10-01T13:00:00+02:00"),
    ],
)
def test_invalid_times_fail_before_discovery_or_saving(env, start, end):
    result = operations.invoke("calendar_draft", {**EVENT, "start": start, "end": end})
    assert result["error"]["code"] == "invalid_time"
    assert not env.connections and not calendar_drafts.store_path().exists()


def test_invalid_revision_rolls_back_without_changing_proposal(env):
    draft = invoke("calendar_draft", **EVENT)
    result = operations.invoke("calendar_update_draft", {**reviewed(draft), "end": "2026-09-01"})
    assert result["error"]["code"] == "invalid_time"
    assert invoke("calendar_read_draft", draft_id=draft["draft_id"]) == draft


def test_creation_attempt_is_committed_before_concurrent_caller(env, monkeypatch):
    draft = invoke("calendar_draft", **EVENT)
    entered, release = Event(), Event()
    put = env.remote.put

    def hold_put(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return put(*args, **kwargs)

    monkeypatch.setattr(env.remote, "put", hold_put)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            calendar_drafts.create, env.account, **reviewed(draft), confirmed=True
        )
        try:
            assert entered.wait(5)
            with pytest.raises(AgentError) as exc:
                calendar_drafts.create(env.account, **reviewed(draft), confirmed=True)
            assert exc.value.code == "calendar_create_unconfirmed"
        finally:
            release.set()
        assert pending.result(timeout=5)["created"]
    assert len(env.remote.puts) == 1


def test_dry_run_creates_no_proposal_and_never_loads_credentials(env, monkeypatch):
    monkeypatch.setattr(auth, "load", lambda: pytest.fail("Credential read"))
    result = operations.invoke("calendar_draft", copy.deepcopy(EVENT), dry_run=True)
    assert result["ok"] and result["data"]["executed"] is False
    assert not calendar_drafts.store_path().exists() and not env.connections
