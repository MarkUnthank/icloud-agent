<h1 align="center">icloud-agent</h1>
<p align="center"><strong>the missing agentic icloud connection</strong></p>

**Read and send iCloud email, draft replies, and manage your calendar from Codex or
another local AI agent.**

Connect your iCloud account once, choose which sender addresses and calendars your
agent can use, then ask for what you need. The connector runs on your computer and
talks directly to Apple.

<p align="center">
  <img src="docs/assets/header.png" alt="icloud-agent — the missing agentic icloud connection" width="100%">
</p>

<p align="center">
  <a href="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml"><img src="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml/badge.svg?branch=main" alt="CI status"></a>
  <a href="https://github.com/MarkUnthank/homebrew-tap"><img src="https://img.shields.io/badge/install-Homebrew-FBB040?logo=homebrew&logoColor=white" alt="Install with Homebrew"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-86b8b5" alt="MIT license"></a>
  <a href="docs/clients.md"><img src="https://img.shields.io/badge/MCP-local%20stdio-24292f" alt="Local stdio MCP"></a>
  <a href="VERIFICATION.md"><img src="https://img.shields.io/badge/status-beta-e2af68" alt="Beta"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/usage.md">Usage</a> ·
  <a href="docs/reference.md">Tool reference</a> ·
  <a href="docs/clients.md">Agent setup</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

## What you can ask

> “Show me the unread emails I received today.”
>
> “Find Alex's email about the invoice and draft a reply.”
>
> “Send that draft from my work address.”
>
> “What's on my calendar tomorrow?”
>
> “Add lunch with Alex at noon on Thursday to my Personal calendar.”

| | What you can do | Current limits |
|---|---|---|
| **Mail** | Search by text, sender, subject, date, or unread status; read messages; draft and send; mark read/unread; archive or move messages | One account; plain-text drafts; attachment metadata only |
| **Calendar** | Check your schedule, find recurring occurrences, and create, edit, or delete personal events in enabled calendars | No recurrence editing, invitations, or RSVP management |

Searching and reading leave unread messages unread. Drafting saves a message without
sending it. When you ask to add an event without naming a calendar, the companion
skill tells your agent to ask which one to use. See [usage](docs/usage.md) for the
full workflows.

## Will it work with my agent?

You need iCloud Mail and Calendar, and an agent that can run a local command or MCP
process on your computer.

| Client | Integration |
|---|---|
| **Codex locally** | `icloud-agent setup --codex` registers MCP and installs the skill |
| **Other local agents** | Use the companion skill and CLI, or run `icloud-agent mcp` as a stdio subprocess |
| **ChatGPT desktop local work** | Plugin included; client/account compatibility is unverified |
| **ChatGPT web, cloud, mobile** | Not supported |

Your computer needs to be awake, online, and able to unlock its credential store.
[Agent and plugin setup →](docs/clients.md)

> **Beta.** App-password discovery has live evidence; draft and send checks have been
> reported by a user. Calendar writes, recipient delivery, and client compatibility
> need further verification. See the [verification record](VERIFICATION.md).

## Quick start

Install with [Homebrew](https://brew.sh/) on macOS:

```sh
brew install MarkUnthank/tap/icloud-agent
icloud-agent setup --codex
icloud-agent auth login
```

You need an iCloud Mail account, Apple Account two-factor authentication, and Codex
on PATH for `setup --codex`.

Login opens Apple's sign-in page, where you generate an **app-specific password**.
Paste it into the terminal's masked prompt; the CLI saves it in your OS credential
store for future use. **Never enter passwords in chat.**

Addresses and calendars load from iCloud automatically. Choose enabled senders and
calendars with **Space** and **Enter**. Your default sender can be an alias different
from your login email. If an address is missing, choose **Add another address…**.
**Sender name** is prefilled from iCloud when available; keep it or edit it to choose
the name recipients see. Change these settings later with `icloud-agent auth configure`.

Once connected, choose **Install agent skills** or **Finish**. Skill installation
includes the shared skill for Codex and other compatible agents, with optional links
for agents such as Claude Code and Windsurf. Extras start unchecked, with a live
selection count at the top. Press **Space** to toggle them, or **Enter** with zero
selected to skip extras and install only the shared skill.

You can install or update skills later with `icloud-agent setup --skills`.
Restart your agent after setup, then try one of the requests above.

Or use the CLI directly:

```sh
icloud-agent mail search
icloud-agent calendar list
icloud-agent schema mail_draft
```

See [setup](docs/setup.md) for `uv`/`pipx` installation, upgrades, and removal.

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
