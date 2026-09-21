# Using the CLI

[← README](../README.md) · [Full operation reference](reference.md)

The CLI accepts structured JSON so agents and scripts can use the same operations.
Every mail/calendar command accepts `--input FILE`, `--input -` for stdin, or `{}` when
omitted. `--dry-run` validates the input schema without reading credentials or connecting
to Apple. It does not validate server state, actual recipients, or calendar semantics.

## Read your inbox

```sh
icloud-agent mail folders
icloud-agent mail search
```

Search for unread messages using JSON on stdin:

```sh
icloud-agent mail search --input - <<'JSON'
{"folder":"INBOX","query":"invoice","unread":true,"limit":10}
JSON
```

`query` is literal text searched across headers and body. It does not parse IMAP or
Gmail expressions: `FROM "Morgan"` searches for those words, not that sender.
Use dedicated fields to filter unread mail by date, sender, and subject:

```sh
icloud-agent mail search --input - --json <<'JSON'
{"unread":true,"since":"2026-09-21","before":"2026-09-22"}
JSON

icloud-agent mail search --input - --json <<'JSON'
{"sender":"person@example.com","subject":"invoice","limit":20}
JSON
```

All supplied filters combine with AND. `sender` matches a substring in the From header,
including its display name; prefer the email address when known. `subject` matches
the Subject header. `since` is inclusive and `before` is exclusive. Both take valid
YYYY-MM-DD dates; when supplied together, `before` must be later than `since`.
They filter the server's INTERNALDATE calendar day, ignoring time and timezone,
as specified by [IMAP](https://www.rfc-editor.org/rfc/rfc9051.html#section-6.4.4).
They do not filter the sender's Date header or express timezone-aware instant bounds.

Results include opaque IDs, headers, `internal_date`, flags, size, and `next_before_uid`.
To get the next page, supply that value as `before_uid` with every other filter unchanged.
`order:"uid_desc"` means most recently added to the folder first. A moved or imported
message can have a high UID and an old date. Compare `internal_date` or the sender's
`date` across relevant pages before claiming a message is newest by that date.

An empty successful search applies only to its actual filters and folder. A failed
search establishes nothing about whether matching messages exist. Use the returned
error's recovery advice; a narrower date range can help a timed-out search.

Read a selected message with its entire `id` (`mail_read` in MCP or `schema`):

```sh
icloud-agent mail read --input - <<'JSON'
{"message_id":"PASTE_ID_FROM_SEARCH"}
JSON
```

Reading uses `BODY.PEEK` and does not mark the message read. The result includes the
body (up to 100,000 characters), content type, attachments' names/types, and `sha256`.
Messages over 20 MiB are rejected. HTML-only bodies may contain HTML; the CLI does not
render HTML or load external images. Attachment contents are not returned.

Treat message IDs as opaque. They contain a folder, UIDVALIDITY, and UID; a move changes
the ID, and a folder rebuild invalidates old IDs. Search again on `stale_id`.

## Draft and send

Create a plain-text draft:

```sh
icloud-agent mail draft --input examples/mail-draft.json
```

The example contains a synthetic recipient. Edit it before using it with a real account.
For a reply, add `reply_to_id` with the original message's ID and select recipients
explicitly. The tool adds reply-thread headers; it does not infer recipients or quote
the original body. `cc` is supported; draft creation has no Bcc input in this release.

Run `icloud-agent mail senders` to list enabled sender addresses and the default. Set
`from_address` in draft input to choose one; omitting it uses the default sender. If no senders
are enabled, drafting and sending are disabled. Apple validates whether your account
can send from a configured alias during SMTP submission.

Drafts include the saved sender name, for example `Alex Example <alex@icloud.com>`.
Setup prefills that name from iCloud and lets you edit it. Change it with
`icloud-agent auth configure`; an existing setup without a saved name needs this once.
For an individual draft, `from_name` overrides the name without changing the email
address or saved setting. `mail senders` returns the saved name as `sender_name`.
Names are set before review and hashing. Sending preserves the reviewed draft's From
header, so a later settings change does not rename an already-saved draft.

Draft creation saves to iCloud Drafts and returns a draft `id` when Apple provides an
APPENDUID response. If it returns only `folder` and `message_id`, the draft was saved:
search that folder for its Message-ID to obtain the ID rather than creating it again.

Drafts and Sent discovery uses the server's special-use flags first. If the relevant
flag is absent, it accepts the exact iCloud names `Drafts` and `Sent Messages`.
Ambiguous or non-selectable folders fail before a draft append or SMTP submission.

Read the saved draft with `mail read`, review it, then send using its returned hash:

```sh
icloud-agent mail send-draft --input - <<'JSON'
{"message_id":"PASTE_DRAFT_ID","expected_sha256":"PASTE_SHA256_FROM_READ"}
JSON
```

Sending accepts only a message in the server's Drafts folder whose From address
is currently enabled in `auth configure`. A changed draft produces `draft_changed`;
read and reassess it before sending.

A successful submission can return:

```json
{
  "ok": true,
  "data": {
    "smtp_accepted": true,
    "delivery_confirmed": false,
    "refused_recipients": [],
    "sent_copy_saved": true,
    "draft_removed": true
  }
}
```

SMTP acceptance means Apple's server accepted the message, not that the recipient
received it. Sent-copy saving and draft cleanup are separate outcomes. The tool
preserves the draft on partial recipient failure. It removes only the unchanged draft
using UID EXPUNGE when available; it never expunges unrelated deleted messages.

**Do not automatically retry an uncertain or partial send.** A persisted journal blocks
another attempt for the same draft ID. On `send_unconfirmed` or `already_attempted`,
check delivery and mailbox state before deciding what to do. Creating a new copy just
to bypass the journal can send a duplicate.

## Organize mail

Use `mail set-read` with `{"message_id":"…","is_read":true}` to mark a message read,
or `false` to mark it unread. The result includes a readback `verified` flag.

Use `mail folders` to discover Archive/Trash by their special-use flags, then
`mail move` with `{"message_id":"…","destination":"EXACT_FOLDER_NAME"}`. The server
must support atomic IMAP MOVE. The tool does not create folders or permanently purge
mail. Search the destination for the message's new ID after a move.

## Read your calendar

```sh
icloud-agent calendar list
```

Only enabled calendars are listed or accessible. Run `icloud-agent auth configure`
to change selections; passing an old event ID cannot bypass a disabled calendar.

Use an exact returned calendar ID and a bounded range:

```sh
icloud-agent calendar search --input - <<'JSON'
{"calendar_id":"PASTE_CALENDAR_ID","start":"2026-10-01","end":"2026-10-08","limit":100}
JSON
```

Date-only ranges are accepted. Search covers at most 366 days and expands recurring
occurrences. If `truncated` is true, narrow the date range. This limit bounds the returned
items, not a server-side pagination request. Occurrences may share the same resource ID.

`calendar read` accepts `{"event_id":"…"}` and returns the complete resource's event
summaries and its ETag. It does not expose an arbitrary CalDAV URL fetch.

## Create, edit, and delete personal events

Copy `examples/calendar-event.json`, replace its calendar ID, and choose your times:

```sh
icloud-agent calendar create --input event.json --dry-run
icloud-agent calendar create --input event.json
```

Timed events require ISO timestamps with UTC offsets, such as
`2026-10-01T10:00:00+02:00`. These express fixed offsets; the CLI does not infer your
IANA timezone or daylight-saving rules. Resolve the correct offset for the event date.
All-day events use dates and an **exclusive** end date: October 1 through October 2
means one all-day event on October 1. Start/end must use the same type, with end later.

To edit, first read the event and then supply its ETag and only fields you want to change:

```sh
icloud-agent calendar update --input - <<'JSON'
{"event_id":"PASTE_EVENT_ID","etag":"\"PASTE_CURRENT_ETAG\"","title":"New title"}
JSON
```

Preserve the returned ETag exactly, including quotes; a JSON writer can help avoid
manual escaping. Updates preserve other iCalendar fields. If another client changes
the event, the server's conditional write rejects the edit with `conflict`.

To delete, use `calendar delete` with the same `event_id` and current `etag`. Recurring
personal series require `whole_series:true`, which removes **all** occurrences.
Individual-occurrence deletion, recurrence creation/editing, meetings with attendees,
and RSVP/invitation handling are not implemented. Use a calendar client for those.

Successful writes report whether readback was verified. A successful write with
`verified:false` needs a follow-up read, not a repeated write.

## Output and exit codes

In a terminal, results use readable labels, grouped records, and color. Set `NO_COLOR=1`
to disable color. Long values wrap; message bodies are displayed as text, not markup.

When stdout is piped or redirected, commands return a JSON envelope automatically.
Agents and scripts should pass `--json` explicitly, including when using a terminal:

```sh
icloud-agent --json auth status
icloud-agent mail search --json
icloud-agent mail search | jq '.data.messages'
```

Successful calls exit 0, failed calls exit 1, and command-line usage errors exit 2.
Interactive login prompts and progress go to stderr, keeping JSON stdout parseable.
Help/version remain human-oriented. MCP uses JSON-RPC on stdout and never adds terminal
styling or banners.

```json
{"ok":true,"data":{"example":"operation-specific result"}}
```

```json
{"ok":false,"error":{"code":"not_authenticated","message":"Run icloud-agent auth login in your terminal once."}}
```

Input validation errors use `error.issues`, containing field paths and messages.
Unknown fields and coercions such as the string `"true"` for a boolean are rejected.
Unexpected protocol errors contain a safe type name, not raw server messages or secrets.
`operation_busy` means the local lock prevented the operation from starting.
`operation_timeout` includes safe operation/stage diagnostics and recovery advice;
it does not mean authentication failed. Read back a timed-out write before retrying.

`icloud-agent call mail_search --input FILE` is equivalent to
`icloud-agent mail search --input FILE`. Use `icloud-agent schema` to discover the live
input schemas, and [troubleshooting](troubleshooting.md) for recovery guidance.
