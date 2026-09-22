"""Account-scoped local event proposals and durable creation attempts."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import date
from uuid import uuid4

from platformdirs import user_state_path

from . import auth, calendar
from .errors import AgentError


def store_path():
    return user_state_path(auth.SERVICE) / "calendar-drafts.sqlite3"


@contextmanager
def store():
    path = store_path()
    auth.private_dir(path.parent)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    with closing(sqlite3.connect(path, timeout=1)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute(
            "CREATE TABLE IF NOT EXISTS drafts ("
            "sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, account TEXT NOT NULL, "
            "revision INTEGER NOT NULL, event TEXT NOT NULL, status TEXT NOT NULL "
            "CHECK (status IN ('draft', 'attempted', 'created')), result TEXT)"
        )
        # Also serialize callers outside the CLI/MCP operation lock.
        db.execute("BEGIN IMMEDIATE")
        yield db


def owner(account):
    return account.apple_account.casefold()


def get(db, account, draft_id):
    row = db.execute(
        "SELECT * FROM drafts WHERE id = ? AND account = ?", (draft_id, owner(account))
    ).fetchone()
    if row is None:
        raise AgentError("draft_not_found", "Calendar draft not found for this account.")
    return row


def snapshot(row):
    event = json.loads(row["event"])
    reviewed = {"draft_id": row["id"], "revision": row["revision"], "event": event}
    digest = hashlib.sha256(
        json.dumps(reviewed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result = {**reviewed, "sha256": digest, "status": row["status"]}
    if row["status"] != "draft":
        result["event_id"] = calendar.event_id(event["calendar_id"], resource_url(row))
    if row["result"]:
        result["creation"] = json.loads(row["result"])
    return result


def resource_url(row):
    return json.loads(row["event"])["calendar_id"].rstrip("/") + "/" + row["id"] + ".ics"


def check_revision(row, expected_sha256):
    if snapshot(row)["sha256"] != expected_sha256:
        raise AgentError(
            "draft_changed", "Calendar draft changed. Read it and confirm the new revision."
        )


def editable(row):
    if row["status"] != "draft":
        raise AgentError(
            "draft_locked",
            "Creation was already attempted. Read the event before taking further action.",
            event_id=snapshot(row)["event_id"],
        )


def validate_event(account, event):
    calendar.check_access(account, event)
    calendar.trusted_url(event["calendar_id"])
    start, end = calendar.parse_time(event["start"]), calendar.parse_time(event["end"])
    calendar.validate_range(start, end)
    return {
        **event,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "all_day": type(start) is date,
    }


def calendar_name(account, calendar_id):
    with calendar.connection(account) as client:
        target = calendar.resolve_calendar(client, calendar_id)
        return str(target.name or "Untitled calendar")


def draft(account, calendar_id, title, start, end, description="", location=""):
    event = validate_event(
        account,
        dict(
            calendar_id=calendar_id,
            title=title,
            start=start,
            end=end,
            description=description,
            location=location,
        ),
    )
    event["calendar_name"] = calendar_name(account, calendar_id)
    draft_id = str(uuid4())
    with store() as db:
        db.execute(
            "INSERT INTO drafts (id, account, revision, event, status) VALUES (?, ?, 1, ?, 'draft')",
            (draft_id, owner(account), json.dumps(event)),
        )
        return snapshot(get(db, account, draft_id))


def drafts(account, limit=20, before=None):
    with store() as db:
        rows = db.execute(
            "SELECT * FROM drafts WHERE account = ? AND (? IS NULL OR sequence < ?) "
            "ORDER BY sequence DESC LIMIT ?",
            (owner(account), before, before, limit + 1),
        ).fetchall()
        return {
            "drafts": [snapshot(row) for row in rows[:limit]],
            "next_before": rows[limit - 1]["sequence"] if len(rows) > limit else None,
        }


def read(account, draft_id):
    with store() as db:
        return snapshot(get(db, account, draft_id))


def update(account, draft_id, expected_sha256, **changes):
    changes = {key: value for key, value in changes.items() if value is not None}
    if not changes:
        raise AgentError("empty_update", "Provide at least one field to change.")
    with store() as db:
        row = get(db, account, draft_id)
        check_revision(row, expected_sha256)
        editable(row)
        previous = json.loads(row["event"])
        event = validate_event(account, {**previous, **changes})
        if event["calendar_id"] != previous["calendar_id"]:
            event["calendar_name"] = calendar_name(account, event["calendar_id"])
        db.execute(
            "UPDATE drafts SET event = ?, revision = revision + 1 WHERE id = ?",
            (json.dumps(event), draft_id),
        )
        return snapshot(get(db, account, draft_id))


def discard(account, draft_id, expected_sha256):
    with store() as db:
        row = get(db, account, draft_id)
        check_revision(row, expected_sha256)
        editable(row)
        db.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    return {"discarded": True, "draft_id": draft_id}


def create(account, draft_id, expected_sha256, confirmed):
    if confirmed is not True:
        raise AgentError("confirmation_required", "Confirm the reviewed calendar draft first.")
    with store() as db:
        row = get(db, account, draft_id)
        check_revision(row, expected_sha256)
        event = validate_event(account, json.loads(row["event"]))
        if row["status"] == "created":
            return {**json.loads(row["result"]), "already_created": True}
        event_ref = calendar.event_id(event["calendar_id"], resource_url(row))
        if row["status"] == "attempted":
            raise AgentError(
                "calendar_create_unconfirmed",
                "Creation was already attempted. Read the returned event_id; do not create a replacement draft.",
                event_id=event_ref,
                draft_id=draft_id,
                retryable=False,
            )
        document = calendar.event_document(
            uid=draft_id,
            title=event["title"],
            start=event["start"],
            end=event["end"],
            description=event["description"],
            location=event["location"],
        )
        with calendar.connection(account) as client:
            calendar.resolve_calendar(client, event["calendar_id"])
            # Commit before PUT: a timeout or process exit may occur after Apple accepts it.
            db.execute("UPDATE drafts SET status = 'attempted' WHERE id = ?", (draft_id,))
            db.commit()
            try:
                response = client.put(
                    resource_url(row),
                    document,
                    headers={"If-None-Match": "*", "Content-Type": "text/calendar; charset=utf-8"},
                )
                calendar.check_write(response, (201, 204))
            except Exception:
                raise AgentError(
                    "calendar_create_unconfirmed",
                    "Event creation did not finish cleanly. Read the returned event_id before taking further action; do not retry or create a replacement draft.",
                    event_id=event_ref,
                    draft_id=draft_id,
                    retryable=False,
                ) from None
            result = {
                **calendar.write_readback(
                    client, event["calendar_id"], resource_url(row), "created"
                ),
                "draft_id": draft_id,
            }
            db.execute(
                "UPDATE drafts SET status = 'created', result = ? WHERE id = ?",
                (json.dumps(result), draft_id),
            )
            return result
