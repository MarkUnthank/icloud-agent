# Verification record

[← README](README.md) · [CI runs](https://github.com/MarkUnthank/icloud-agent/actions/workflows/test.yml)

## What the automated checks establish

Tests use synthetic data and protocol doubles for Apple services. A real subprocess
exercises the stdio MCP handshake, tool discovery, and unauthenticated error path.
The suite requires no Apple Account and performs no live mailbox/calendar writes.

The v0.2.0 local suite has **37 passing tests on macOS / Python 3.14**. CI tests Python 3.11 and 3.14 on Linux. macOS tests are run locally to avoid
GitHub-hosted macOS runner charges; the initial release also passed the former macOS CI jobs.
Consult current CI runs for remote results. CI also checks lint/format, generated reference drift, local doc links,
example schemas, version consistency, package building, and isolated wheel installation.

The v0.3.0 suite has **68 passing tests locally on macOS / Python 3.14**.
A local pseudo-terminal walkthrough used synthetic credentials and mocked verification/
storage to check prompt layout and hidden password entry. It did not authenticate with Apple.

The development branch's Apple web-session experiment has **129 passing tests locally
on macOS / Python 3.14**, including password/2FA handling, session reuse, failed and
cancelled sign-in, native-store serialization, suppression of plaintext cookie files,
TLS enforcement, rejection of redirects to non-Apple destinations, strict alias parsing,
and exclusion of unrelated Mail preferences. Its commands were installed and checked locally.

The subsequent agent-skill installer brings the suite to **151 passing tests locally
on macOS / Python 3.14**. Coverage includes the shared directory, relative agent links,
explicit copies and symlink fallback, custom agent paths, unmanaged content preservation,
migration of the old managed Codex copy, and rollback after a failed filesystem commit.
Optional installation is tested separately from successful authentication and is omitted
from JSON/piped login output.

The installed CLI was also exercised in an isolated home directory: it installed the
shared skill and a relative Claude Code link without invoking a subprocess. Local
`setup --codex` migrated the previous managed skill, and Codex configuration readback
confirmed the enabled connection used `/opt/homebrew/bin/icloud-agent mcp`.

## Live read checks — September 21, 2026

On Apple Silicon macOS / Python 3.14, the user completed `auth web-login` in their own
terminal. A separate process then loaded the native Keychain session and validated it
with Apple. Subsequent processes reused it without receiving a password or 2FA code.
The current Mail preferences route returned ten active addresses: primary addresses,
three aliases expanded across their supported domains, and four custom-domain addresses.
The parser also found the configured iCloud default sender. The web Mail query returned
twelve folders. The setup discovery path then returned the web alias inventory and
four CalDAV calendars, with the existing default sender present and the account config
unchanged. No message bodies were read and no Mail/Calendar writes were performed.

The older native alias endpoint returned HTTP 403 with the same session; the current
web preferences endpoint succeeded. CalDAV discovery had separately returned ten email
identities and four calendars using the existing app-specific password. These observations
cover one account and do not prove long-term session lifetime or every account configuration.

## Automated coverage

Covered behavior:

- Space/arrow/Enter picker interaction, cancellation without saving, concurrent settings
  replacement, disabled calendar IDs, empty selections, and enabled sender discovery.
- Disabled draft sender rejection before SMTP and alias envelope selection with the
  primary address used for SMTP authentication. These use protocol doubles.

- Terminal/JSON routing, explicit JSON in a TTY, usage exit codes, `NO_COLOR`, literal
  rendering of untrusted content, prompt routing, and failed-login behavior.
- Credential-store interface, config permissions, account replacement/logout, and absence
  of password values in saved config or account repr. Tests use a fake keychain.
- Strict input validation, safe errors, and dry-run avoiding credential/network access.
- Mail UIDVALIDITY, BODY.PEEK reads, recipient checks, unchanged-draft checks, one-attempt
  sending, uncertain-send blocking, and targeted UID expunge.
- Calendar time validation, host/redirect restrictions, resource paths, ETags, preservation
  of unknown fields, and recurrence/attendee mutation boundaries.
- MCP initialization, 14 schemas/annotations, and a safe unauthenticated response.
- Installer wiring in an isolated fake home with mocked package installation/registration.
- Bundled plugin/skill export, custom `CODEX_HOME`, unmanaged configuration protection,
  and preservation of stable executable symlinks across package-manager upgrades.

The local installer has additionally been exercised on macOS without login. Codex
configuration readback showed an enabled stdio connection using the installed absolute
executable; the separately installed wheel exposed all 13 tools. Plugin/skill structure
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

- Live mail-message reads and writes, SMTP sending, and calendar event mutations.
- Long-term web-session expiry/recovery and live verification on additional accounts.
- Native Windows/Linux credential stores and Windows installation.
- ChatGPT desktop plugin installation, tool invocation, and account-specific availability.
- Delivery, server-created Sent copies, and cleanup after a real send.

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
