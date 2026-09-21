import base64
import json
from contextlib import contextmanager
from datetime import UTC, date, datetime
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import caldav
from icalendar import Calendar, Event

from .auth import Account
from .errors import AgentError


def trusted_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not (host == "icloud.com" or host.endswith(".icloud.com"))
    ):
        raise AgentError(
            "invalid_calendar_url", "Calendar URLs must be HTTPS resources on icloud.com."
        )
    return url


class AppleDAVClient(caldav.DAVClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.session.request

        def apple_request(method, url, **options):
            options["allow_redirects"] = False
            for _ in range(6):
                trusted_url(str(url))
                response = request(method, url, **options)
                if response.status_code not in (301, 302, 307, 308):
                    return response
                location = response.headers.get("Location")
                if not location:
                    return response
                url = trusted_url(urljoin(str(url), location))
            raise AgentError("redirect_limit", "iCloud returned too many redirects.")

        self.session.request = apple_request

    def request(self, url, method="GET", body="", headers=None, **kwargs):
        trusted_url(str(url))
        return super().request(url, method, body, headers, **kwargs)


@contextmanager
def connection(account: Account):
    with AppleDAVClient(
        url="https://caldav.icloud.com",
        username=account.apple_account,
        password=account.password,
        timeout=30,
        require_tls=True,
        enable_rfc6764=False,
        rate_limit_handle=False,
    ) as client:
        yield client


def discover(account: Account):
    with connection(account) as c:
        return [{"id": trusted_url(str(x.url)), "name": x.name} for x in c.principal().calendars()]


def calendars(account: Account):
    return [item for item in discover(account) if item["id"] in account.calendar_ids]


def check_access(account: Account, values: dict):
    calendar_id = values.get("calendar_id")
    if "event_id" in values:
        try:
            calendar_id, _ = json.loads(base64.urlsafe_b64decode(values["event_id"]))
            if not isinstance(calendar_id, str):
                raise ValueError()
        except Exception:
            raise AgentError(
                "invalid_id", "Use an event ID returned by calendar search/read/create."
            ) from None
    if calendar_id is not None and calendar_id not in account.calendar_ids:
        raise AgentError(
            "calendar_disabled", "Calendar is not enabled. Run icloud-agent auth configure."
        )


def resolve_calendar(client, calendar_id: str):
    trusted_url(calendar_id)
    for calendar in client.principal().calendars():
        if str(calendar.url) == calendar_id:
            return calendar
    raise AgentError("not_found", "Choose a calendar ID returned by calendar list.")


def event_id(calendar_id: str, url: str) -> str:
    return base64.urlsafe_b64encode(json.dumps([calendar_id, url]).encode()).decode()


def resolve_event(client, ref: str):
    try:
        calendar_id, url = json.loads(base64.urlsafe_b64decode(ref))
        trusted_url(calendar_id)
        trusted_url(url)
        cp, ep = urlsplit(calendar_id), urlsplit(url)
        relative = unquote(ep.path)[len(unquote(cp.path).rstrip("/")) + 1 :]
        if (
            cp.netloc != ep.netloc
            or not unquote(ep.path).startswith(unquote(cp.path).rstrip("/") + "/")
            or not relative
            or "/" in relative
            or relative in (".", "..")
        ):
            raise ValueError()
    except Exception:
        raise AgentError(
            "invalid_id", "Use an event ID returned by calendar search/read/create."
        ) from None
    resolve_calendar(client, calendar_id)
    return calendar_id, url


def parse_time(value: str):
    try:
        if len(value) == 10:
            return date.fromisoformat(value)
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result
    except ValueError:
        raise AgentError(
            "invalid_time",
            "Use YYYY-MM-DD for all-day events, or an ISO timestamp "
            "including its UTC offset, e.g. 2026-09-22T10:00:00+02:00.",
        ) from None


def validate_range(start, end):
    if type(start) is not type(end) or end <= start:
        raise AgentError(
            "invalid_time",
            "End must follow start and both must be dates or timed values. "
            "All-day end dates are exclusive.",
        )


def serialize_event(component):
    result = {
        "uid": str(component.get("UID", "")),
        "title": str(component.get("SUMMARY", "")),
        "description": str(component.get("DESCRIPTION", "")),
        "location": str(component.get("LOCATION", "")),
        "recurring": "RRULE" in component or "RDATE" in component,
        "has_attendees": "ATTENDEE" in component,
    }
    for field in ("DTSTART", "DTEND", "RECURRENCE-ID"):
        value = component.get(field)
        result[field.lower().replace("dt", "")] = value.dt.isoformat() if value else None
    return result


def read_resource(client, calendar_id: str, url: str):
    response = client.request(url)
    if response.status == 404:
        raise AgentError("not_found", "Calendar event no longer exists.")
    if response.status != 200:
        raise AgentError("calendar_read_failed", f"Calendar read returned HTTP {response.status}.")
    data = response.raw
    parsed = Calendar.from_ical(data)
    return {
        "id": event_id(calendar_id, url),
        "etag": response.headers.get("Etag"),
        "events": [serialize_event(x) for x in parsed.walk("VEVENT")],
    }, parsed


def read(account: Account, event_id: str):
    with connection(account) as c:
        calendar_id, url = resolve_event(c, event_id)
        result, _ = read_resource(c, calendar_id, url)
        return result


def search(account: Account, calendar_id: str, start: str, end: str, limit: int = 100):
    start_at, end_at = parse_time(start), parse_time(end)
    validate_range(start_at, end_at)
    if (end_at - start_at).days > 366:
        raise AgentError("range_too_large", "Search at most 366 days at a time.")
    with connection(account) as c:
        calendar = resolve_calendar(c, calendar_id)
        items = calendar.search(start=start_at, end=end_at, event=True, expand=True)
        result = []
        for item in items[:limit]:
            result.append(
                {
                    "id": event_id(calendar_id, trusted_url(str(item.url))),
                    "events": [serialize_event(x) for x in item.icalendar_instance.walk("VEVENT")],
                }
            )
        return {
            "events": result,
            "truncated": len(items) > limit,
            "note": "Occurrences share a resource ID. Read an event to obtain its ETag before editing.",
        }


def create(
    account: Account,
    calendar_id: str,
    title: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
):
    start_at, end_at = parse_time(start), parse_time(end)
    validate_range(start_at, end_at)
    uid = str(uuid4())
    component = Event()
    for key, value in {
        "UID": uid,
        "DTSTAMP": datetime.now(UTC),
        "SUMMARY": title,
        "DTSTART": start_at,
        "DTEND": end_at,
        "DESCRIPTION": description,
        "LOCATION": location,
    }.items():
        component.add(key, value)
    doc = Calendar()
    doc.add("PRODID", "-//icloud-agent//EN")
    doc.add("VERSION", "2.0")
    doc.add_component(component)
    with connection(account) as c:
        calendar = resolve_calendar(c, calendar_id)
        url = str(calendar.url).rstrip("/") + "/" + uid + ".ics"
        response = c.put(
            url,
            doc.to_ical().decode(),
            headers={"If-None-Match": "*", "Content-Type": "text/calendar; charset=utf-8"},
        )
        check_write(response, (201, 204))
        return write_readback(c, calendar_id, url, "created")


def check_write(response, expected):
    if response.status == 412:
        raise AgentError(
            "conflict", "Event changed in another client. Read it again before editing."
        )
    if response.status not in expected:
        raise AgentError(
            "calendar_write_failed",
            f"Calendar write returned HTTP {response.status}. Read back state before retrying.",
        )


def write_readback(client, calendar_id, url, action):
    try:
        result, _ = read_resource(client, calendar_id, url)
        return {action: True, "verified": True, **result}
    except Exception:
        return {
            action: True,
            "verified": False,
            "id": event_id(calendar_id, url),
            "note": "Write succeeded but readback failed. Read this ID; do not repeat the write.",
        }


def update(
    account: Account,
    event_id: str,
    etag: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
):
    if all(x is None for x in (title, start, end, description, location)):
        raise AgentError("empty_update", "Provide at least one field to change.")
    with connection(account) as c:
        calendar_id, url = resolve_event(c, event_id)
        result, doc = read_resource(c, calendar_id, url)
        if not etag or result["etag"] != etag:
            raise AgentError("conflict", "Event changed. Read it again before editing.")
        components = doc.walk("VEVENT")
        # Avoid silently altering a series or sending invitations. Recurrence editing needs
        # explicit occurrence/series semantics, which this release does not implement.
        if len(components) != 1 or any(
            k in components[0] for k in ("RRULE", "RDATE", "RECURRENCE-ID", "ATTENDEE", "ORGANIZER")
        ):
            raise AgentError(
                "unsupported_event",
                "This release edits standalone personal events only. "
                "Recurring events and meetings can be read but must be edited in Calendar.",
            )
        component = components[0]
        for key, value in {
            "SUMMARY": title,
            "DESCRIPTION": description,
            "LOCATION": location,
            "DTSTART": start,
            "DTEND": end,
        }.items():
            if value is not None:
                component.pop(key, None)
                component.add(key, parse_time(value) if key in ("DTSTART", "DTEND") else value)
        if "DTEND" not in component:
            raise AgentError("invalid_time", "Provide an explicit end time for this event.")
        validate_range(component["DTSTART"].dt, component["DTEND"].dt)
        component.pop("DURATION", None)
        sequence = int(component.get("SEQUENCE", 0)) + 1
        for key, value in {
            "SEQUENCE": sequence,
            "DTSTAMP": datetime.now(UTC),
            "LAST-MODIFIED": datetime.now(UTC),
        }.items():
            component.pop(key, None)
            component.add(key, value)
        response = c.put(
            url,
            doc.to_ical().decode(),
            headers={"If-Match": etag, "Content-Type": "text/calendar; charset=utf-8"},
        )
        check_write(response, (204,))
        return write_readback(c, calendar_id, url, "updated")


def delete(account: Account, event_id: str, etag: str, whole_series: bool = False):
    with connection(account) as c:
        calendar_id, url = resolve_event(c, event_id)
        result, doc = read_resource(c, calendar_id, url)
        if not etag or result["etag"] != etag:
            raise AgentError("conflict", "Event changed. Read it again before deleting.")
        components = doc.walk("VEVENT")
        if any("ATTENDEE" in x or "ORGANIZER" in x for x in components):
            raise AgentError("unsupported_event", "Delete meetings with attendees in Calendar.")
        if not whole_series and (
            len(components) > 1
            or any(any(k in x for k in ("RRULE", "RDATE", "RECURRENCE-ID")) for x in components)
        ):
            raise AgentError(
                "series_scope_required",
                "This deletes the entire recurring series. "
                "Set whole_series only if that is what the user requested.",
            )
        response = c.request(url, "DELETE", headers={"If-Match": etag})
        check_write(response, (200, 204))
        try:
            verified = c.request(url).status == 404
        except Exception:
            verified = False
        return {"deleted": True, "verified": verified}
