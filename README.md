<p align="center">
  <img src="docs/assets/header.png" alt="icloud-agent — the missing agentic icloud connection" width="100%">
</p>

<h1 align="center">icloud-agent</h1>
<p align="center"><strong>the missing agentic icloud connection</strong></p>

<p align="center">
  <a href="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml"><img src="https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml/badge.svg?branch=main" alt="CI status"></a>
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

Give your local agent access to iCloud Mail and Calendar. Search your inbox, prepare a
reply, or manage your day through a CLI, a companion skill, or 13 MCP tools—all backed
by the same implementation.

**Runs on your computer. Connect once. Invoke when you need it.** There is no hosted
backend, public endpoint, subscription to this project, or background daemon. Your
agent starts a local process and connects directly to Apple over TLS.

> **Early release.** Automated tests and local MCP transport are verified. Live iCloud
> account behavior and ChatGPT desktop integration still need acceptance testing.
> See the [verification record](VERIFICATION.md) for the precise boundary.

## Quick start

You need **Python 3.11+**, Git, an iCloud Mail account, an OS credential store, and
Apple Account two-factor authentication. macOS is the primary development platform.

```sh
# Download the source.
git clone https://github.com/MarkUnthank/icloud-agent.git
cd icloud-agent

# Install the CLI and skill, register MCP with Codex, and connect iCloud.
python3 install.py --codex --login
```

Setup opens Apple's account page. Generate an **app-specific password**, then enter
it into the hidden terminal prompt. It is saved in your OS credential store and
reused by the CLI and MCP tools. **Enter it in your terminal, never in chat.**

Restart Codex after installation, then try:

> “Use iCloud Agent to show my unread emails.”
>
> “Check my calendar for tomorrow.”
>
> “Draft a reply to this email.”

Prefer the terminal?

```sh
icloud-agent mail search
icloud-agent calendar list
icloud-agent schema mail_draft
```

Omit `--codex` for another agent or a CLI-only installation. The installer prints an
absolute executable path if `icloud-agent` is not on your PATH. See
[installation, upgrades, and removal](docs/setup.md) for `pipx`, `uv`, Windows/Linux
notes, and the complete authentication walkthrough. **This project is not published
to PyPI; use this repository or its release artifacts.**

## What it can do

| | Available now | Boundaries |
|---|---|---|
| **Mail** | Search/read messages, save drafts, send reviewed drafts, mark read/unread, move to Archive/Trash or another folder | Plain-text drafts; attachment metadata only; one account |
| **Calendar** | List calendars, find events and recurring occurrences, create/edit/delete personal events | No recurrence editing, invitations, or RSVP management |
| **Agents** | CLI + skill, local stdio MCP, packaged desktop plugin | Requires a client with local execution; no web/cloud bridge |

Read/search operations leave mail unread. Sending requires the current draft's
content hash; editing an event requires its current ETag. These checks catch changed
drafts and concurrent calendar edits before overwriting someone else's work.

A local journal prevents another send attempt for the same draft ID. If SMTP ends
ambiguously, the tool stops instead of guessing whether it should resend. The result
distinguishes SMTP acceptance from actual delivery. [Details and examples →](docs/usage.md)

## Where it runs

| Client | Integration |
|---|---|
| **Codex locally** | `install.py --codex` registers MCP and installs the skill |
| **Other local agents** | Run `icloud-agent mcp` as a stdio subprocess, or invoke the CLI |
| **ChatGPT desktop local work** | Plugin packaged; actual client/account compatibility needs validation |
| **ChatGPT web, cloud, mobile** | No local bridge provided |

Your computer needs to be awake, online, and able to unlock its credential store.
The agent may keep the MCP child process alive for the session; no system service is
installed. [Agent and plugin setup →](docs/clients.md)

## Your data

- Credentials live in macOS Keychain, Windows Credential Manager, or Linux Secret Service.
- The project has no telemetry and operates no intermediary server.
- Account addresses and a minimal send journal are stored locally; inbox bodies are not cached.
- Data returned to an AI client enters that client's context. **Local tools do not make the model offline.**

See [security and privacy](docs/security.md) for storage locations, access boundaries,
and removal, or [report a vulnerability privately](SECURITY.md).

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

Bug reports, focused improvements, and carefully documented live compatibility
results are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) to set up development,
run the checks, and open a pull request. Please keep account data out of issues.

Maintained by [Mark Unthank](https://github.com/MarkUnthank). See the
[changelog](CHANGELOG.md) for changes. This is an independent project, not affiliated
with or endorsed by Apple or OpenAI. iCloud is a trademark of Apple Inc.

## License

[MIT](LICENSE). The source, skill, and included project artwork may be redistributed
under this project's license; dependencies retain their respective licenses.
