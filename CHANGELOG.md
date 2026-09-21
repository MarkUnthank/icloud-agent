# Changelog

User-visible changes are recorded here. This project is pre-1.0; CLI/tool interfaces
may change between releases. Release artifacts and notes are available on
[GitHub Releases](https://github.com/MarkUnthank/icloud-agent/releases).

## Unreleased

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
