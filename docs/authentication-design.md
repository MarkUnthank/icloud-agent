# Authentication and access decisions

[← Architecture](architecture.md)

## App-password setup

The connector opens Apple's account-management page. The user generates an
app-specific password there, pastes it into a hidden terminal prompt, and chooses
access. The connector stores that password in the native OS credential store.
It never needs the main Apple Account password or a browser cookie.

[Apple's app-specific-password instructions](https://support.apple.com/en-us/102654)
require two-factor authentication. Generation remains a manual step on Apple's page;
this project has not established a supported password-generation API.

## Discovery and selection

CalDAV supplies the calendar inventory. The terminal picker uses Questionary and
supports arrow keys, Space to toggle, Enter to save, and Ctrl-C to cancel. Calendars
start unchecked on first login. `auth configure` restores existing selections;
new calendars stay unchecked. Selecting none enables none.

The app-password connection does not provide a documented sender-alias inventory.
The primary mail address is offered automatically; users enter additional existing
aliases once and choose a default sender independently of the mailbox login address.
These are local settings, not a verified list of Apple-owned addresses.
Apple checks permission during SMTP submission. Setup does not send test messages.
Aliases can be disabled and re-enabled without retyping them.

## Enforcement

The shared operation dispatcher checks calendar IDs before event reads or writes,
including the calendar encoded in opaque event IDs. Calendar listing filters disabled
resources. CLI and MCP use the same dispatcher. Operations and configuration saves
share a lock; a configuration session also checks for concurrent account replacement
before committing its choices.

Draft creation and sending check the currently enabled sender list. This also prevents
sending an old draft from an address that has since been disabled. The SMTP login
continues to use the mailbox address; the selected alias supplies the From identity
and SMTP envelope. `mail_senders` exposes enabled addresses to agents.

Sender selections do **not** partition the shared inbox. The connector can read messages
delivered to any alias of that mailbox. Calendar selections restrict both reads and writes.

Settings are saved only after the prompts complete. Cancellation preserves previous
settings. Versions before 0.3 did not store explicit access selections; their account
files require a new login rather than implicitly enabling all resources.

## Possible future authorization

Apple documents authorization for supported third-party apps:
[access iCloud data in third-party apps](https://support.apple.com/en-us/121539).
Its [developer iCloud OAuth request endpoint](https://developer.apple.com/contact/request/icloud-oauth2/)
redirected to Developer sign-in when checked on September 21, 2026. Enrollment,
scopes, public/native-client support, local redirects, and alias enumeration remain
unverified. No enrollment request has been submitted.

Official authorization could replace app passwords if it supports this project's
local-only distribution model. Private iCloud.com request replay is not used.
