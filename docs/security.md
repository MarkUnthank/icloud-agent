# Security and privacy

[← README](../README.md) · [Report a vulnerability](../SECURITY.md)

## Data path

Your local CLI/MCP process connects directly to Apple's IMAP, SMTP, and CalDAV services
over TLS. The project operates no proxy, has no telemetry, and makes no OpenAI API
calls itself. Installing/updating the Python package contacts package registries; a
login may open Apple's account page in your default browser.

Email and calendar results go to whichever client invoked the tools. If that client
uses a hosted AI model, relevant results enter its context and are subject to its own
data handling. Local execution does not make the model or conversation offline.

## Credentials

Authentication uses an Apple app-specific password saved through an explicitly selected
native backend: macOS Keychain, Windows Credential Manager, or Linux Secret Service.
There is no plaintext keyring fallback, password argument, environment-variable login,
browser-cookie extraction, or hidden main-account password storage. The credential is
available in process memory while making requests to Apple.

The OS may prompt to unlock or allow access to its credential store. Any process
running with equivalent access under your account may still be able to use the same
credential: this is not isolation from an already-compromised local user account.

The password is revocable at Apple. It is not a fine-grained read-only token or a set
of per-tool permission scopes. It supports both mail and calendar access for this tool.
The account config contains only the Apple Account and iCloud Mail addresses.

## Local state

Application paths use `platformdirs`. Defaults are:

| Platform | Account config | Send journal and operation lock |
|---|---|---|
| macOS | `~/Library/Application Support/icloud-agent/account.json` | `~/Library/Application Support/icloud-agent/` |
| Linux | `~/.config/icloud-agent/account.json` | `~/.local/state/icloud-agent/` |
| Windows | `%LOCALAPPDATA%\icloud-agent\icloud-agent\account.json` | `%LOCALAPPDATA%\icloud-agent\icloud-agent\` |

Linux XDG variables may override defaults. The local installer's runtime/plugin
location is distinct from platformdirs on some platforms; see [setup](setup.md).
The journal consists of `send-*.json` files; the lock is `operations.lock`.

Private directories/config files receive restrictive POSIX permissions. Windows file
protection relies on the user's profile/ACLs and its native credential manager; a POSIX
mode is not a complete Windows ACL policy. Native Windows/Linux credential stores have
not been live-tested by this project.

The journal contains Message-ID and submission status and may contain refused recipient
addresses. It stores no subject or body. Inbox messages/events are not persistently
cached by the tool. Your client, shell redirection, or input JSON files may store data
separately. Delete sensitive input/output files when you no longer need them.

`auth logout` removes the active config and keychain credential but retains the journal.
Removing the journal removes duplicate-attempt protection. To remove the integration
completely, follow [removal instructions](setup.md#remove) and revoke the app-specific
password at Apple.

## Writes and untrusted content

Mail bodies, subjects, event descriptions, and other fetched content are untrusted
input. The skill directs agents to treat them as data, not instructions to run commands,
send mail, disclose information, or change other resources. This instruction is guidance
for the agent, not a guarantee against all prompt-injection attacks.

The shared operation layer validates strict input schemas and serializes local mutations.
Mail references include UIDVALIDITY. Calendar writes use conditional ETags. A draft's
content must match the hash read before sending. These checks reduce stale writes;
they do not determine whether the user's intent authorizes an action.

The CLI provides write capability to the local user. Authorization and confirmation
remain the invoking client's responsibility. An instruction to draft does not mean send.
MCP annotations describe actions but do not enforce account-level read/write separation.

SMTP has no universal exactly-once delivery guarantee. The tool records intent before
submitting and blocks repeated attempts for that draft ID, including uncertain failures.
This can require manual investigation even when a failed attempt never reached Apple.
It cannot deduplicate a manually copied/new draft or a journal that has been removed.

## Reporting

Never include passwords, message bodies, real recipient lists, calendar details, or
account configs in a public issue. Use the repository's
[private vulnerability reporting](https://github.com/MarkUnthank/icloud-agent/security/advisories/new)
for suspected security issues. See [SECURITY.md](../SECURITY.md) for scope.
