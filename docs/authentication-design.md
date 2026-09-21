# Authentication and access decisions

[← Architecture](architecture.md)

## App-password setup

The connector opens Apple's account-management page. The user generates an
app-specific password there, pastes it into a hidden terminal prompt, and chooses
access. The connector stores that password in the native OS credential store.
This connection does not need the main Apple Account password or a browser cookie.
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

When a valid web session is saved for the same login email, setup uses the iCloud Mail
sender inventory instead. It expands the primary and alias local parts across Apple's
supported domains, adds custom-domain identities, and omits inactive aliases from the
picker. Apple's `allowSendFrom` flags and default sender are returned separately by
`web-check`; they do not replace the user's local access selections. If the session is
missing, expired, or unavailable, discovery uses the CalDAV identities.

The native account's older `/cc/wm/alias.json` route returned HTTP 401 with an app password
and HTTP 403 with the web session. Apple's current web preferences route succeeded.
An endpoint failure was not evidence that aliases were inaccessible.

## Apple Account web-session experiment

`auth web-login` accepts the normal Apple Account password and a device or SMS
verification code in the user's own terminal. It uses
[pyicloud 2.7.0](https://github.com/timlaing/pyicloud/tree/2.7.0) for Apple's SRP password
handshake, 2FA, trusted-session exchange, and iCloud service discovery. The dependency
is pinned because the in-memory adapter uses its session and password internals.
Changes to that pin require reviewing those integration points and running the auth tests.

The main password and verification code are never saved. A separate native credential
entry, service `icloud-agent-web`, holds the reusable session tokens and cookies.
The adapter disables pyicloud's automatic plaintext session/cookie files before making
requests. It enforces HTTPS, certificate verification, and Apple-hosted destinations,
including redirects. It does not import cookies from a browser or read other apps'
credentials. Existing app-password settings and access selections remain separate.

`auth web-status` validates the session against Apple. `auth web-login` reuses a valid
session without asking for a password; an expired session requires sign-in again.
There is no unattended password login or background renewal. Code-based 2FA is supported;
hardware security keys and legacy two-step verification are not implemented in this flow.
Updated Apple terms must be reviewed on iCloud.com by the user.

`auth web-check` reads sender settings from
GET `/cc/mail/v1/account/{dsid}/preference/web/all` and queries folders through
POST `/mailws2/v1/geqs/query` with a mailbox-domain query. Both routes were located in
[Apple's public web client](https://www.icloud.com/system/icloud.com/2634Build25/en-gb/main.js).
The preferences response includes unrelated forwarding, rules, and auto-reply settings;
the parser returns only sender identities and the default sender. Folder output is a
count, capped at 100. No message bodies, cookies, or tokens are returned.
These are private Apple APIs whose behavior may change.
Tests cover authentication state, cancellation, 2FA failure, credential persistence,
redirect rejection, and request shapes using synthetic data. A successful unit test
does not establish live alias discovery or Mail access. On September 21, 2026, a real
user completed password/2FA sign-in locally. Fresh CLI processes reused the Keychain
session and retrieved ten active sender addresses, the iCloud default, and twelve
Mail folders. See the [verification record](../VERIFICATION.md).

This experiment does not generate an app-specific password, replace the standard
Mail/Calendar operations, or expand their configured access. Normal message/event
operations still use the app-specific password with IMAP, SMTP, and CalDAV.

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
local-only distribution model. The web-session experiment uses private iCloud APIs;
the standard Mail and Calendar operations still use IMAP, SMTP, and CalDAV.
