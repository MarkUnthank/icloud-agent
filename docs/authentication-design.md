# Authentication and access decisions

[← Architecture](architecture.md)

## App-password setup

The connector opens Apple's account-management page. The user generates an
app-specific password there, pastes it into a hidden terminal prompt, and chooses
access. The connector stores that password in the native OS credential store.
It never needs the main Apple Account password or a browser cookie.
Setup asks for one login email and uses it for IMAP, SMTP, and CalDAV.

[Apple's app-specific-password instructions](https://support.apple.com/en-us/102654)
require two-factor authentication. Generation remains a manual step on Apple's page;
this project has not established a supported password-generation API.

## Discovery and selection

CalDAV supplies the calendar inventory. The terminal picker uses Questionary and
supports arrow keys, Space to toggle, Enter to save, and Ctrl-C to cancel. Calendars
start unchecked on first login. `auth configure` restores existing selections;
new calendars stay unchecked. Selecting none enables none.

The same CalDAV connection reads the principal's `calendar-user-address-set` property
([RFC 6638, section 2.4.1](https://www.rfc-editor.org/rfc/rfc6638.html#section-2.4.1)).
Discovery accepts valid `mailto:` identities, ignores principal URLs and UUIDs, and
deduplicates addresses. Setup combines these with the login email and previously
saved addresses before showing the sender picker. New addresses stay unchecked.
Users choose a default sender independently of the login email. The picker
also offers **Add another address…** for an existing Mail address missing from discovery.

These are account calendar identities, not a guaranteed complete Mail alias inventory
or proof of SMTP permission. A live app-password check on September 21, 2026 returned
ten email identities, including iCloud, legacy me.com, and custom-domain addresses.
It included both previously configured senders and the chosen default. No personal
addresses or credentials are included in test fixtures. Apple checks permission during
SMTP submission; setup does not send test messages.

The native Mac account metadata advertised `/cc/wm/alias.json` on Apple's partitioned
MCC service. A read-only request with the app-specific password returned HTTP 401.
The built-in browser reached iCloud Mail sign-in; authenticated web alias responses
have not yet been captured. Neither result rules out a browser-session alias API.

## Enforcement

The shared operation dispatcher checks calendar IDs before event reads or writes,
including the calendar encoded in opaque event IDs. Calendar listing filters disabled
resources. CLI and MCP use the same dispatcher. Operations and configuration saves
share a lock; a configuration session also checks for concurrent account replacement
before committing its choices.

Draft creation and sending check the currently enabled sender list. This also prevents
sending an old draft from an address that has since been disabled. The SMTP login
uses the login email; the selected alias supplies the From identity
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
scopes, public/native-client support, local redirects, and OAuth-based alias enumeration
remain unverified. No enrollment request has been submitted.

Official authorization could replace app passwords if it supports this project's
local-only distribution model. Private iCloud.com request replay is not used.
