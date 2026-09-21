<p align="center">
  <img src="docs/assets/header.png" alt="icloud-agent — the missing agentic icloud connection" width="100%">
</p>

<h1 align="center">icloud-agent</h1>
<p align="center"><strong>the missing agentic icloud connection</strong></p>

<p align="center">
  <a href="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml"><img src="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml/badge.svg?branch=main" alt="CI status"></a>
  <a href="https://github.com/MarkUnthank/homebrew-tap"><img src="https://img.shields.io/badge/install-Homebrew-FBB040?logo=homebrew&logoColor=white" alt="Install with Homebrew"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-86b8b5" alt="MIT license"></a>
  <a href="docs/clients.md"><img src="https://img.shields.io/badge/MCP-local%20stdio-24292f" alt="Local stdio MCP"></a>
  <a href="VERIFICATION.md"><img src="https://img.shields.io/badge/status-alpha-e2af68" alt="Alpha: live iCloud verification pending"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/usage.md">Usage</a> ·
  <a href="docs/reference.md">Tool reference</a> ·
  <a href="docs/clients.md">Agent setup</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

Give your local agent access to iCloud Mail and Calendar. Search your inbox, draft
replies, and manage events through a CLI, companion skill, or local MCP connection.

**Runs on your computer. Connect once. Invoke when you need it.**

> **Alpha.** Live iCloud account behavior remains unverified. See the
> [verification record](VERIFICATION.md) for completed tests and remaining checks.

## Quick start

Install with [Homebrew](https://brew.sh/) on macOS:

```sh
brew install MarkUnthank/tap/icloud-agent
icloud-agent setup --codex
icloud-agent auth login
```

You need an iCloud Mail account, Apple Account two-factor authentication, and Codex
on PATH for `setup --codex`.

Login shows Apple's sign-in URL; press Enter to open it. Generate an **app-specific password** and enter it
in the hidden terminal prompt. It is saved in your OS credential store for future
invocations. **Enter it in your terminal, never in chat.**

Addresses and calendars load from iCloud automatically. Choose enabled senders and
calendars with **Space** and **Enter**, then pick your default sender. Change your
choices later with `icloud-agent auth configure`.

Restart Codex, then try:

> “Use iCloud Agent to show my unread emails.”
>
> “Check my calendar for tomorrow.”
>
> “Draft a reply to this email.”

Or use the CLI:

```sh
icloud-agent mail search
icloud-agent calendar list
icloud-agent schema mail_draft
```

See [setup](docs/setup.md) for `uv`/`pipx` installation, upgrades, and removal.

## What it can do

| | Available now | Boundaries |
|---|---|---|
| **Mail** | Search/read messages, save drafts, send reviewed drafts, mark read/unread, move to Archive/Trash or another folder | Plain-text drafts; attachment metadata only; one account |
| **Calendar** | List calendars, find events and recurring occurrences, create/edit/delete personal events | No recurrence editing, invitations, or RSVP management |

Reading and searching leave mail unread. See [usage](docs/usage.md) for sending and
editing workflows.

## Where it runs

| Client | Integration |
|---|---|
| **Codex locally** | `icloud-agent setup --codex` registers MCP and installs the skill |
| **Other local agents** | Run `icloud-agent mcp` as a stdio subprocess, or invoke the CLI |
| **ChatGPT desktop local work** | Plugin included; client/account compatibility is unverified |
| **ChatGPT web, cloud, mobile** | Not supported |

Your computer needs to be awake, online, and able to unlock its credential store.
[Agent and plugin setup →](docs/clients.md)

## Your data

- Credentials live in macOS Keychain, Windows Credential Manager, or Linux Secret Service.
- The connector talks directly to Apple, with no intermediary server or telemetry.
- Account addresses and a send journal are stored locally; inbox bodies are not cached.
- Mail and calendar data returned to an AI client enter that client's context.

Read [security and privacy](docs/security.md), or [report a vulnerability privately](SECURITY.md).

## Documentation

| Guide | What's inside |
|---|---|
| [Setup](docs/setup.md) | Install, authenticate, upgrade, switch accounts, uninstall |
| [Usage](docs/usage.md) | Copyable mail/calendar workflows and JSON output |
| [CLI & MCP reference](docs/reference.md) | Every operation, input, default, and constraint |
| [Agent setup](docs/clients.md) | Codex, generic MCP clients, skill, desktop plugin |
| [Troubleshooting](docs/troubleshooting.md) | Login, keychain, PATH, conflicts, uncertain sends |
| [Architecture](docs/architecture.md) | How the CLI, MCP, protocols, and state fit together |
| [Verification](VERIFICATION.md) | What has been tested and what remains unverified |

## Contributing

Bug reports, improvements, and live compatibility results are welcome. Start with
[CONTRIBUTING.md](CONTRIBUTING.md), [community conduct](CODE_OF_CONDUCT.md), or the
[support guide](SUPPORT.md).

Maintained by [Mark Unthank](https://github.com/MarkUnthank). [Changelog →](CHANGELOG.md)

## License

[MIT](LICENSE), including the source, skill, and project artwork. Dependencies retain
their own licenses.

Independent project; not affiliated with Apple or OpenAI. iCloud is a trademark of Apple Inc.
