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
| Command not found | For Homebrew, use `"$(brew --prefix)/bin/icloud-agent"` and follow Homebrew's shell setup instructions. For uv/pipx, check the manager's bin directory is on PATH. Desktop clients may not inherit your shell PATH; rerun `setup --codex` to register the absolute path. |
| Old version after a Homebrew install | Run `which -a icloud-agent`. An old `~/.local/bin` symlink may shadow Homebrew; follow [migration](setup.md#switching-from-the-original-source-installer). |
| `setup_conflict` | An unmanaged skill or MCP entry has the same name. Inspect and rename/remove it yourself before rerunning setup. Existing content is preserved. |
| `codex_missing` | Install the Codex CLI and make it available on PATH, or run `setup` without `--codex` for another local client. |
| Homebrew first install takes several minutes | The formula currently builds native dependencies. Let Homebrew finish; later command invocations do not compile or download code. |
| Python too old / missing venv | Install Python 3.11+ with venv support. On Windows use `py -3`. On Linux your distribution may provide `python3-venv`. |
| `setup_required` | Run `icloud-agent auth login` to explicitly select access after upgrading an older account config. |
| `calendar_disabled` / `sender_disabled` | Run `icloud-agent auth configure` in your terminal to review enabled resources. An empty selection enables none. |
| `config_changed` | Another login, logout, or configuration session changed account settings. Restart `auth configure`; the stale selection was not saved. |
| `not_authenticated` | Run `icloud-agent auth login` in your own terminal. A config file alone is insufficient; the OS credential entry must exist. |
| `interactive_login_required` | Login was launched from a pipe/agent session. Open a normal interactive terminal yourself. |
| `invalid_password_format` | Use the generated `xxxx-xxxx-xxxx-xxxx` app-specific password, not your main Apple Account password. |
| Keychain/Secret Service access fails | Unlock your OS login session/credential store and allow the app if prompted. On Linux confirm a Secret Service provider and D-Bus user session are running. There is no plaintext fallback. |
| Login or `--check` fails | Check internet access, the login email, iCloud Mail enablement, and whether Apple revoked the password. `--check` tests IMAP and CalDAV; SMTP is checked only on send. |
| `authentication_failed` | Apple rejected the IMAP login. Check the login email and app-specific password with `auth login`. This is distinct from a timeout. |
| MCP tool not visible | Restart the client; verify `codex mcp get icloud-agent`; check the absolute executable path. Avoid registering both the plugin and standalone server. |
| `invalid_arguments` | Read `error.issues` and `icloud-agent schema OPERATION`. JSON types are strict and extra fields are rejected. |
| `stale_id` / `not_found` | The message/event moved, disappeared, or its folder changed IDs. Search again; don't reuse an old ID blindly. |
| `folder_not_found` | Inspect `mail folders`. Special-folder discovery prefers a unique special-use flag, then an exact iCloud name: `Drafts`, `Sent Messages`, or `Deleted Messages`. Ambiguous or non-selectable matches are rejected. For `mail move`, copy the exact returned destination name. |
| Sender/date search returns unexpected or no messages | `query` is literal text in headers/body. Use `sender`, `subject`, `since`, and `before` fields for filters; see [search examples](usage.md#read-your-inbox). `FROM` or `SINCE` inside `query` are searched as words. An empty result from the wrong filters does not answer the intended search. |
| `message_too_large` | Reads are capped at 20 MiB per message. Use your mail client for this message. |
| `draft_changed` | Read and review the draft again before supplying its new hash. |
| `send_unconfirmed` / `already_attempted` | Delivery may have occurred. Check Sent, any refused recipients, and actual delivery. Do not clear the journal or create a new draft merely to bypass protection. |
| SMTP accepted, housekeeping failed | The message may have been sent even if Sent-copy saving/draft cleanup failed. Do not resend based on those flags alone. |
| `conflict` | The event ETag is stale or another client changed it during the write. Read the current event and reassess the edit. |
| `invalid_time` | Use dates for all-day events or timestamps with UTC offsets. End must follow start, use the same type, and be exclusive for all-day events. |
| `unsupported_event` | Recurring edits and attendee meetings aren't supported. Use your calendar client. |
| `series_scope_required` | Deleting this resource removes the whole recurring series. Only set `whole_series:true` when that is the intended action. |
| `range_too_large` / truncated events | Narrow the date range; search supports at most 366 days and bounded returned results. |
| `operation_busy` | Another local operation holds the lock. The requested mail/calendar operation has not started (`executed:false`). Wait, then retry sequentially. Do not remove a live lock file. |
| `operation_timeout` | Read `operation`, `stage`, and `recovery`. IMAP errors also include `service` and `timeout_seconds`. A search/fetch timeout may improve with a date range or sender/subject filter. Connect/login timeouts call for checking connectivity, not replacing credentials. A failed search is not evidence of no matches. Read back a timed-out write before considering another attempt. |
| `operation_failed` after a write | Its final state may be uncertain. Read back the resource first. The tool does not assume a transport error means nothing changed. |

## Need to report a bug?

Include version, OS/Python, command family, error code/operation/stage, and a minimal
synthetic reproduction. Say whether it is a protocol-double test or a live iCloud
observation. Do not include account JSON, keychain exports, message bodies, or real IDs.

[Open a bug report](https://github.com/MarkUnthank/icloud-agent/issues/new?template=bug_report.yml).
For credential exposure or other vulnerabilities, [report privately](../SECURITY.md).
