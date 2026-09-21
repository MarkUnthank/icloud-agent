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

The terminal presentation update has **52 passing tests locally on macOS / Python 3.14**.
A local pseudo-terminal walkthrough used synthetic credentials and mocked verification/
storage to check prompt layout and hidden password entry. It did not authenticate with Apple.

Covered behavior:

- Terminal/JSON routing, explicit JSON in a TTY, usage exit codes, `NO_COLOR`, literal
  rendering of untrusted content, prompt routing, and failed-login behavior.
- Credential-store interface, config permissions, account replacement/logout, and absence
  of password values in saved config or account repr. Tests use a fake keychain.
- Strict input validation, safe errors, and dry-run avoiding credential/network access.
- Mail UIDVALIDITY, BODY.PEEK reads, recipient checks, unchanged-draft checks, one-attempt
  sending, uncertain-send blocking, and targeted UID expunge.
- Calendar time validation, host/redirect restrictions, resource paths, ETags, preservation
  of unknown fields, and recurrence/attendee mutation boundaries.
- MCP initialization, 13 schemas/annotations, and a safe unauthenticated response.
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

- Live IMAP, SMTP, and CalDAV behavior against an authenticated iCloud account.
- Real keychain persistence through the full authenticated setup flow.
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
