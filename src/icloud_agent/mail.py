import base64
import hashlib
import json
import re
import smtplib
import ssl
from contextlib import contextmanager
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid

from imapclient import IMAPClient

from .auth import Account
from .errors import AgentError

MAX_MESSAGE = 20 * 1024 * 1024


@contextmanager
def connection(account: Account):
    with IMAPClient("imap.mail.me.com", ssl=True, timeout=30) as client:
        client.login(account.mail_address, account.password)
        yield client


def encode_ref(folder: str, validity: int, uid: int) -> str:
    return base64.urlsafe_b64encode(json.dumps([folder, validity, uid]).encode()).decode()


def decode_ref(ref: str):
    try:
        folder, validity, uid = json.loads(base64.urlsafe_b64decode(ref))
        if not isinstance(folder, str) or not folder or type(uid) is not int or uid < 1:
            raise ValueError()
        if type(validity) is not int or validity < 1:
            raise ValueError()
        return folder, validity, uid
    except Exception:
        raise AgentError(
            "invalid_id", "Use a message ID returned by mail search or read."
        ) from None


def select_ref(client, ref: str, readonly: bool = True):
    folder, validity, uid = decode_ref(ref)
    status = client.select_folder(folder, readonly=readonly)
    if status[b"UIDVALIDITY"] != validity:
        raise AgentError("stale_id", "This folder's IDs changed. Search again before continuing.")
    return folder, uid


def special_folder(client, flag: bytes) -> str:
    matches = [name for flags, _, name in client.list_folders() if flag in flags]
    if len(matches) != 1:
        raise AgentError(
            "folder_not_found", "Could not uniquely discover the iCloud special folder."
        )
    return matches[0]


def folders(account: Account):
    with connection(account) as c:
        return [
            {"name": name, "flags": [f.decode() for f in flags]}
            for flags, _, name in c.list_folders()
        ]


def search(
    account: Account,
    folder: str = "INBOX",
    query: str = "",
    unread: bool = False,
    limit: int = 20,
    before_uid: int | None = None,
):
    with connection(account) as c:
        status = c.select_folder(folder, readonly=True)
        criteria = ["UNSEEN"] if unread else ["ALL"]
        if query:
            criteria += ["TEXT", query]
        if before_uid is not None:
            if before_uid <= 1:
                return {"messages": [], "next_before_uid": None}
            criteria += ["UID", f"1:{before_uid - 1}"]
        ids = sorted(c.search(criteria, charset="UTF-8"), reverse=True)
        chosen = ids[:limit]
        data = (
            c.fetch(
                chosen,
                [
                    "BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)]",
                    "FLAGS",
                    "RFC822.SIZE",
                ],
            )
            if chosen
            else {}
        )
        result = []
        for uid in chosen:
            row = data.get(uid)
            if row is None:
                continue
            raw = next((v for k, v in row.items() if k.startswith(b"BODY[")), b"")
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            result.append(
                {
                    "id": encode_ref(folder, status[b"UIDVALIDITY"], uid),
                    "uid": uid,
                    "subject": str(msg.get("Subject", "")),
                    "from": str(msg.get("From", "")),
                    "to": str(msg.get("To", "")),
                    "date": str(msg.get("Date", "")),
                    "flags": [f.decode() for f in row.get(b"FLAGS", [])],
                    "bytes": row.get(b"RFC822.SIZE"),
                }
            )
        return {"messages": result, "next_before_uid": chosen[-1] if len(ids) > limit else None}


def fetch_message(c, uid: int) -> bytes:
    metadata = c.fetch([uid], ["RFC822.SIZE"])
    if uid not in metadata:
        raise AgentError("not_found", "Message no longer exists in this folder.")
    if metadata[uid][b"RFC822.SIZE"] > MAX_MESSAGE:
        raise AgentError("message_too_large", "Message exceeds the 20 MiB read limit.")
    row = c.fetch([uid], ["BODY.PEEK[]"]).get(uid, {})
    if b"BODY[]" not in row:
        raise AgentError("not_found", "Message disappeared while reading it.")
    return row[b"BODY[]"]


def read(account: Account, message_id: str):
    with connection(account) as c:
        _, uid = select_ref(c, message_id)
        raw = fetch_message(c, uid)
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    body = msg.get_body(preferencelist=("plain", "html"))
    content = body.get_content() if body else ""
    if not isinstance(content, str):
        content = ""
    return {
        "id": message_id,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "subject": str(msg.get("Subject", "")),
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "cc": str(msg.get("Cc", "")),
        "date": str(msg.get("Date", "")),
        "message_id": str(msg.get("Message-ID", "")),
        "body": content[:100_000],
        "body_truncated": len(content) > 100_000,
        "content_type": body.get_content_type() if body else None,
        "attachments": [
            {"filename": p.get_filename(), "content_type": p.get_content_type()}
            for p in msg.iter_attachments()
        ],
    }


def recipients(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if "\r" in value or "\n" in value:
            raise AgentError("invalid_address", "Email addresses cannot contain line breaks.")
        parsed = getaddresses([value])
        if len(parsed) != 1 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+", parsed[0][1]):
            raise AgentError("invalid_address", "Use one complete email address per recipient.")
        # SMTPUTF8 not currently negotiated for internationalized mailbox local parts.
        try:
            parsed[0][1].encode("ascii")
        except UnicodeEncodeError:
            raise AgentError(
                "invalid_address", "Internationalized mailbox addresses are unsupported."
            ) from None
        result.append(parsed[0][1])
    return result


def enabled_sender(account: Account, address: str | None):
    if address is None:
        address = next(iter(account.sender_addresses), None)
    if address is None or address.casefold() not in {
        item.casefold() for item in account.sender_addresses
    }:
        raise AgentError(
            "sender_disabled", "Sender is not enabled. Run icloud-agent auth configure."
        )
    return recipients([address])[0]


def draft(
    account: Account,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    reply_to_id: str | None = None,
    from_address: str | None = None,
):
    recipients(to + (cc or []))
    if not to:
        raise AgentError("invalid_address", "At least one To recipient is required.")
    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = enabled_sender(account, from_address)
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    with connection(account) as c:
        if reply_to_id:
            _, uid = select_ref(c, reply_to_id)
            original = BytesParser(policy=policy.default).parsebytes(fetch_message(c, uid))
            original_id = original.get("Message-ID")
            if not original_id:
                raise AgentError(
                    "missing_message_id", "Original message has no Message-ID for threading."
                )
            msg["In-Reply-To"] = str(original_id)
            msg["References"] = (
                str(original.get("References", "")) + " " + str(original_id)
            ).strip()
        folder = special_folder(c, b"\\Drafts")
        response = c.append(folder, msg.as_bytes(), flags=[b"\\Draft"])
        match = re.search(rb"APPENDUID (\d+) (\d+)", response)
        if match:
            ref = encode_ref(folder, int(match[1]), int(match[2]))
            return {"id": ref, "message_id": msg["Message-ID"], "saved": True}
        return {
            "saved": True,
            "folder": folder,
            "message_id": msg["Message-ID"],
            "note": "Search this folder for Message-ID before sending; draft was appended.",
        }


def set_read(account: Account, message_id: str, is_read: bool):
    with connection(account) as c:
        _, uid = select_ref(c, message_id, readonly=False)
        if uid not in c.fetch([uid], ["FLAGS"]):
            raise AgentError("not_found", "Message no longer exists.")
        (c.add_flags if is_read else c.remove_flags)([uid], [b"\\Seen"])
        result = c.fetch([uid], ["FLAGS"])
        verified = uid in result and (b"\\Seen" in result[uid][b"FLAGS"]) == is_read
        return {"id": message_id, "is_read": is_read, "verified": verified}


def move(account: Account, message_id: str, destination: str):
    with connection(account) as c:
        folder, uid = select_ref(c, message_id, readonly=False)
        if folder == destination:
            return {"id": message_id, "moved": False, "reason": "Already in destination."}
        if destination not in [name for _, _, name in c.list_folders()]:
            raise AgentError("folder_not_found", "Choose a destination returned by mail folders.")
        if uid not in c.fetch([uid], ["FLAGS"]):
            raise AgentError("not_found", "Message no longer exists.")
        if not c.has_capability("MOVE"):
            raise AgentError(
                "unsupported", "Server lacks atomic MOVE; no copy/delete fallback attempted."
            )
        c.move([uid], destination)
        return {
            "moved": True,
            "destination": destination,
            "note": "Search the destination for the new message ID.",
        }


def send_draft(account: Account, message_id: str, expected_sha256: str, state_dir):
    """Send only a reviewed, unchanged draft; journal prevents accidental repeated submission."""
    key = hashlib.sha256(message_id.encode()).hexdigest()
    journal = state_dir / f"send-{key}.json"
    if journal.exists():
        raise AgentError(
            "already_attempted",
            "This draft has already had a send attempt. "
            "Check Sent and the recipient before composing another; it will not be retried.",
        )
    with connection(account) as c:
        drafts = special_folder(c, b"\\Drafts")
        folder, uid = select_ref(c, message_id, readonly=False)
        if folder != drafts:
            raise AgentError(
                "not_a_draft", "Only messages in the server's Drafts folder can be sent."
            )
        raw = fetch_message(c, uid)
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise AgentError("draft_changed", "Draft changed. Read it again before sending.")
        msg = BytesParser(policy=policy.SMTP).parsebytes(raw)
        sender = recipients([str(msg.get("From", ""))])
        if len(msg.get_all("From", [])) != 1 or len(sender) != 1:
            raise AgentError("invalid_sender", "Draft must have exactly one From address.")
        enabled_sender(account, sender[0])
        if msg.get("Sender") is not None:
            raise AgentError("unsupported", "Separate Sender headers are unsupported.")
        if any(h.lower().startswith("resent-") for h in msg.keys()):
            raise AgentError("unsupported", "Resent-* draft headers are unsupported.")
        targets = [
            a
            for _, a in getaddresses(
                msg.get_all("To", []) + msg.get_all("Cc", []) + msg.get_all("Bcc", [])
            )
        ]
        recipients(targets)
        if not targets:
            raise AgentError("invalid_address", "Draft has no recipients.")
        sent = special_folder(c, b"\\Sent")
        # Persist intent before SMTP: interruption after DATA has an inherently ambiguous outcome.
        with journal.open("x") as f:
            journal.chmod(0o600)
            json.dump({"status": "attempted", "message_id": str(msg.get("Message-ID", ""))}, f)
            f.flush()
            import os

            os.fsync(f.fileno())
        try:
            with smtplib.SMTP("smtp.mail.me.com", 587, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(account.mail_address, account.password)
                refused = smtp.send_message(msg, from_addr=sender[0], to_addrs=targets)
        except Exception:
            raise AgentError(
                "send_unconfirmed",
                "SMTP submission did not finish cleanly. Delivery may "
                "have occurred. Do not retry; check Sent/recipient first.",
            ) from None
        result = {
            "smtp_accepted": True,
            "delivery_confirmed": False,
            "refused_recipients": list(refused),
            "sent_copy_saved": False,
            "draft_removed": False,
        }
        # send_message strips Bcc from the wire; keep it in the owner's Sent copy.
        try:
            c.append(sent, msg.as_bytes(), flags=[b"\\Seen"])
            result["sent_copy_saved"] = True
            # Do not remove a draft edited in another client while SMTP was in flight.
            unchanged = hashlib.sha256(fetch_message(c, uid)).hexdigest() == expected_sha256
            if not refused and unchanged and c.has_capability("UIDPLUS"):
                c.delete_messages([uid])
                c.expunge([uid])  # UID EXPUNGE only; never expunge unrelated deleted mail.
                result["draft_removed"] = True
        except Exception:
            result["note"] = (
                "SMTP accepted the message; mailbox housekeeping was incomplete. Do not resend."
            )
        journal.write_text(json.dumps(result))
        return result
