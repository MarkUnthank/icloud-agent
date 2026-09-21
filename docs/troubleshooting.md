# Troubleshooting

[← README](../README.md) · [Setup](setup.md)

Start with the version and a local credential check:

```sh
icloud-agent --version
icloud-agent auth status
```

Then use `auth status --check` to test Apple connectivity. Do not send a message merely
to diagnose read access. Errors intentionally omit raw protocol messages because they
can include private data. Avoid enabling library debug logging on your real account.

| Symptom or error | Meaning and next step |
|---|---|
| Command not found | Use the absolute executable printed by the installer, or add `~/.local/bin` to PATH on macOS/Linux. A desktop client may not inherit your shell PATH. |
| Python too old / missing venv | Install Python 3.11+ with venv support. On Windows use `py -3`. On Linux your distribution may provide `python3-venv`. |
| `not_authenticated` | Run `icloud-agent auth login` in your own terminal. A config file alone is insufficient; the OS credential entry must exist. |
| `interactive_login_required` | Login was launched from a pipe/agent session. Open a normal interactive terminal yourself. |
| `invalid_password_format` | Use the generated `xxxx-xxxx-xxxx-xxxx` app-specific password, not your main Apple Account password. |
| Keychain/Secret Service access fails | Unlock your OS login session/credential store and allow the app if prompted. On Linux confirm a Secret Service provider and D-Bus user session are running. There is no plaintext fallback. |
| Login or `--check` fails | Check internet access, both account addresses, iCloud Mail enablement, and whether Apple revoked the password. `--check` tests IMAP and CalDAV; SMTP is checked only on send. |
| MCP tool not visible | Restart the client; verify `codex mcp get icloud-agent`; check the absolute executable path. Avoid registering both the plugin and standalone server. |
| `invalid_arguments` | Read `error.issues` and `icloud-agent schema OPERATION`. JSON types are strict and extra fields are rejected. |
| `stale_id` / `not_found` | The message/event moved, disappeared, or its folder changed IDs. Search again; don't reuse an old ID blindly. |
| `folder_not_found` | Discover exact folders with `mail folders`. The tool requires a unique server-advertised special folder for Drafts/Sent. |
| `message_too_large` | Reads are capped at 20 MiB per message. Use your mail client for this message. |
| `draft_changed` | Read and review the draft again before supplying its new hash. |
| `send_unconfirmed` / `already_attempted` | Delivery may have occurred. Check Sent, any refused recipients, and actual delivery. Do not clear the journal or create a new draft merely to bypass protection. |
| SMTP accepted, housekeeping failed | The message may have been sent even if Sent-copy saving/draft cleanup failed. Do not resend based on those flags alone. |
| `conflict` | The event ETag is stale or another client changed it during the write. Read the current event and reassess the edit. |
| `invalid_time` | Use dates for all-day events or timestamps with UTC offsets. End must follow start, use the same type, and be exclusive for all-day events. |
| `unsupported_event` | Recurring edits and attendee meetings aren't supported. Use your calendar client. |
| `series_scope_required` | Deleting this resource removes the whole recurring series. Only set `whole_series:true` when that is the intended action. |
| `range_too_large` / truncated events | Narrow the date range; search supports at most 366 days and bounded returned results. |
| `operation_failed` with `Timeout` | Another local mutation may still hold the lock. Check its outcome before retrying. Don't remove a live lock file. |
| `operation_failed` after a write | Its final state may be uncertain. Read back the resource first. The tool does not assume a transport error means nothing changed. |

## Need to report a bug?

Include version, OS/Python, command family, redacted error code/type, and a minimal
synthetic reproduction. Say whether it is a protocol-double test or a live iCloud
observation. Do not include account JSON, keychain exports, message bodies, or real IDs.

[Open a bug report](https://github.com/MarkUnthank/icloud-agent/issues/new?template=bug_report.yml).
For credential exposure or other vulnerabilities, [report privately](../SECURITY.md).
