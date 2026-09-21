# Verification record

[← README](README.md) · [CI runs](https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml)

## What the automated checks establish

Tests use synthetic data and protocol doubles for Apple services. A real subprocess
exercises the stdio MCP handshake, tool discovery, and unauthenticated error path.
The suite requires no Apple Account and performs no live mailbox/calendar writes.

The calendar-draft feature passed **188 tests locally on macOS / Python 3.14**.
Regression cases cover persistent account-scoped drafts, pagination, revisions and
stale hashes, strict confirmation, discarding, disabled destinations, fixed-offset
and all-day times, conditional creation, failed readback, HTTP/transport failures,
interruption, and concurrent attempts. A second creation cannot issue another PUT.
The real MCP subprocess advertises all 19 tools. Lint/format, generated schemas,
80 local documentation links, four example inputs, and skill validation passed.
These are synthetic transport tests; the new workflow has not been tested against a
live iCloud calendar.

Before the calendar-draft feature, the full suite passed **160 tests locally on macOS / Python 3.14** during merge
preparation on September 21, 2026, including sender-name regression cases. Lint,
formatting, generated references, 79 local documentation links, three example schemas,
release metadata, and skill/plugin validation passed. Source and wheel builds passed.

A fresh isolated wheel installation verified the current mail-search and sender-name
schemas, plugin export, shared skill installation, and absence of the removed web-auth
modules. Synthetic keyboard input verified the optional agent picker's live selection
count and Enter-to-skip behavior. The app-password success card and skill-installation
result were previously checked in Ghostty using the isolated setup preview.

CI tests Python 3.11 and 3.14 on Linux. macOS tests run locally to avoid
GitHub-hosted macOS runner charges. Consult current CI runs for remote results.
CI also checks lint/format, generated reference drift, local doc links, example schemas,
version consistency, package building, and isolated wheel installation.

Agent-skill installer coverage includes the shared directory, relative agent links,
explicit copies and symlink fallback, custom agent paths, unmanaged content preservation,
migration of the old managed Codex copy, and rollback after a failed filesystem commit.
Optional installation is tested separately from successful authentication and is omitted
from JSON/piped login output.

Earlier installation checks exercised the CLI in an isolated home directory: it installed the
shared skill and a relative Claude Code link without invoking a subprocess. Local
`setup --codex` migrated the previous managed skill, and Codex configuration readback
confirmed the enabled connection used `/opt/homebrew/bin/icloud-agent mcp`.

The current build and shared skill were installed locally and compared with source.
Removed web-auth modules and their dependency were absent. The saved app-specific
password passed a live IMAP/CalDAV check after the update. Account settings and send
journal files were unchanged; only the obsolete web-session credential was removed.

## Live evidence — September 21, 2026

On Apple Silicon macOS / Python 3.14, discovery using the saved app-specific password
returned ten email identities and four calendars. The identities included the configured
senders and chosen default. This covers one account; CalDAV identities are not a
guaranteed complete alias inventory or proof of sending permission for each address.
An additional read using the same app-specific password returned the principal's
human-readable `DAV:displayname`. This verifies an account-name suggestion, not per-alias
Mail display-name preferences.

The user supplied an agent's report of successful message reading, draft creation,
draft read/hash verification, SMTP submission, Sent-folder readback, and draft removal.
No recipients were refused; recipient-inbox delivery was not verified. That run needed
a local runtime patch because `Drafts` lacked a special-use flag. `Sent Messages` did
have its `\Sent` flag. The source now includes the fallback and regression tests.
These are user-reported live results, not an independently repeated acceptance run.

The same report exposed invalid conclusions from searches: IMAP expressions supplied
in `query` were searched literally. The earlier claim of no unread mail on a given
day and a claim about the newest message from a sender remain unverified. Dedicated
filter fields and clearer skill instructions address the cause; offline tests do not
establish the real mailbox's contents. No live mail or calendar writes were repeated
while implementing these fixes.

## Automated coverage

Covered behavior:

- Literal full-text queries; separate sender/subject/date filters; valid date bounds;
  IMAPClient wire serialization; UID pagination and server internal dates.
- Safe search-stage timeouts, explicit IMAP authentication rejection, and real local
  lock contention. A failed search cannot return an empty success result.
- Special-use flag precedence and exact iCloud folder-name fallbacks; ambiguous and
  non-selectable folders rejected; unflagged Drafts with flagged Sent covered through
  the draft/send flow. SMTP timeout still blocks a repeated attempt.
- Space/arrow/Enter picker interaction, cancellation without saving, concurrent settings
  replacement, disabled calendar IDs, empty selections, and enabled sender discovery.
- Disabled draft sender rejection before SMTP and alias envelope selection with the
  primary address used for SMTP authentication. These use protocol doubles.
- Editable account-name suggestions, saved sender names, per-draft name overrides,
  Unicode display names, and header-injection rejection. SMTP submission preserves the
  reviewed draft's From header and uses the address alone for its envelope.

- Terminal/JSON routing, explicit JSON in a TTY, usage exit codes, `NO_COLOR`, literal
  rendering of untrusted content, prompt routing, and failed-login behavior.
- Credential-store interface, config permissions, account replacement/logout, and absence
  of password values in saved config or account repr. Tests use a fake keychain.
- Strict input validation, safe errors, and dry-run avoiding credential/network access.
- Mail UIDVALIDITY, BODY.PEEK reads, recipient checks, unchanged-draft checks, one-attempt
  sending, uncertain-send blocking, and targeted UID expunge.
- Calendar time validation, host/redirect restrictions, resource paths, ETags, preservation
  of unknown fields, and recurrence/attendee mutation boundaries.
- Local calendar draft persistence and account isolation, revision-bound confirmation,
  draft discard, one creation attempt, and UTC encoding of fixed-offset times.
- MCP initialization, tool schemas/annotations, and a safe unauthenticated response.
- Installer wiring in an isolated fake home with mocked package installation/registration.
- Bundled plugin/skill export, custom `CODEX_HOME`, unmanaged configuration protection,
  and preservation of stable executable symlinks across package-manager upgrades.

The local installer has additionally been exercised on macOS without login. Codex
configuration readback showed an enabled stdio connection using the installed absolute
executable. Plugin/skill structure
validators passed. These checks are not proof of live Apple behavior or use in ChatGPT.

A v0.2.0 wheel was installed in a fresh environment and `setup` exported its plugin
and skill from outside the checkout. The CLI version and schema-only invocation passed.
The published v0.2.0 source archive was installed through Homebrew on Apple Silicon
macOS. Formula style, strict audit, dependency/source checksum verification, and
`brew test` passed. `setup --codex` installed the bundled skill and registered
`/opt/homebrew/bin/icloud-agent`; Codex readback confirmed an enabled stdio connection.
The initial source build took approximately six minutes after dependencies were present.
The formula applies Homebrew's `ENV.O0` only while building qh3, whose AWS-LC entropy
implementation requires unoptimized C. Compiler output confirmed `-O0` and the build passed.
The [tap CI](https://github.com/MarkUnthank/homebrew-tap/actions/workflows/tests.yml) validates
formula syntax on Linux. Full Homebrew installation tests run locally on macOS; no
GitHub-hosted macOS runner is used. The earlier clean-macOS-runner attempt was cancelled.

## What is still unverified

- Independent repetition of the reported live mail read/draft/send flow with this source build.
- Calendar event mutations and live verification on additional accounts.
- Native Windows/Linux credential stores and Windows installation.
- ChatGPT desktop plugin installation, tool invocation, and account-specific availability.
- Recipient-inbox delivery and server-created Sent-copy behavior (separate from the tool's copy).

## Live acceptance procedure

Perform these steps only on an account you own or are explicitly authorized to test.
Record version/commit, OS/client version, the operation, and observed readback without
storing private account data in this repository.

1. Run `icloud-agent auth login` in your own terminal. Generate an Apple app-specific
   password when instructed; enter it in the hidden prompt. Verify with `auth status --check`.
2. Restart the agent and list mail folders/calendars. Read a chosen message/event and
   confirm mail reads do not change its unread state.
3. With explicit intent to test writes, create a disposable draft and personal event.
   Confirm them in a separate iCloud client, update the event, and remove test resources.
4. Only when explicitly requested, send a reviewed draft to a mailbox you control.
   Confirm actual delivery, Sent-copy behavior, and draft cleanup independently.
   SMTP acceptance alone does not prove delivery.
5. Exercise the exact desktop agent/plugin surface and record its version. Don't infer
   ChatGPT web/mobile or another client's support from an MCP subprocess test.

Report live compatibility evidence through a sanitized issue or PR. A future release
should update this record only when the corresponding checks actually happened.
