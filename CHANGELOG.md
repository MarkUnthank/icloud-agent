# Changelog

User-visible changes are recorded here. This project is pre-1.0; CLI/tool interfaces
may change between releases. Release artifacts and notes are available on
[GitHub Releases](https://github.com/MarkUnthank/icloud-agent/releases).

## Unreleased

- Remove repeated setup hints and shorten the bundled agent skill. Show interrupted-write
  guidance only when cancelling a write; picker keys now say Enter continues the flow.

- Load iCloud account email identities through CalDAV during login and configuration;
  show them directly in the sender picker and preserve the selected default. Manual
  additions are available inside the picker for addresses Apple omits.

- Handle bracketed password pastes without submitting copied newlines; trim outer whitespace,
  mask input, and require Enter to continue.

- Show Apple's full sign-in URL and wait for Enter before opening the browser during login.

- Ask for one iCloud login email for Mail and Calendar. Let an enabled alias be chosen
  as the default sender independently of the login email.

## 0.3.0 — 2026-09-21

- Interactive sender/calendar selection with Space and Enter during login and `auth configure`.
- Automatic calendar discovery; existing sender aliases can be entered manually.
- Selected calendar access enforced for CLI and MCP, including opaque event IDs.
- `mail_senders` and `mail_draft.from_address`; sending rechecks the enabled sender.
- Empty selections enable nothing; newly discovered calendars require explicit selection.
- Upgrading from 0.2.x requires `auth login` to choose access; account settings are not implicitly migrated.

- Terminal presentation with cyan headings, grouped records, readable errors, and progress.
- Guided login with default email input, inline validation, and hidden password entry.
- Automatic JSON when stdout is piped; `--json` forces machine output in a terminal.
- `NO_COLOR` support and terminal control-character filtering for external content.
- Agent skill explicitly requests JSON; MCP output stays unchanged.

## 0.2.0 — 2026-09-21

- Homebrew distribution through `MarkUnthank/tap/icloud-agent`.
- Packaged `setup --codex` command installs the skill and registers local MCP without a checkout.
- Every wheel includes the desktop plugin and skill; setup respects `CODEX_HOME`.
- Package-manager installation, upgrade, migration, and removal documentation.

## 0.1.0 — 2026-09-21

Initial public preview.

### Added

- Local CLI, companion skill, and 13 stdio MCP tools for iCloud Mail and Calendar.
- Interactive app-specific-password setup with native OS credential storage.
- Mail search/read, plain-text drafts, reviewed-draft sending, read flags, and folder moves.
- Calendar discovery/search/read and personal event create/update/delete.
- Draft hash checks, a persistent send-attempt journal, UIDVALIDITY checks, and conditional calendar writes.
- Local installer, Codex registration, desktop plugin packaging, and MIT license.
- Setup, usage, generated reference, security, troubleshooting, architecture, and contributor guides.
- Automated tests, CI package checks, dependency update configuration, and issue/PR templates.

### Verification boundary

The CLI, local install, and MCP transport have been exercised. Apple operations are
covered by protocol doubles; live account behavior and ChatGPT desktop integration
still need acceptance testing. Recurrence editing, invitation/RSVP handling, and
attachment transfer are not included. See [VERIFICATION.md](VERIFICATION.md).
