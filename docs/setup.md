# Installation and authentication

[← README](../README.md) · [Troubleshooting](troubleshooting.md)

## Homebrew (macOS)

```sh
brew install MarkUnthank/tap/icloud-agent
icloud-agent setup --codex
icloud-agent auth login
```

Homebrew installs an isolated Python runtime and dependencies. You do not need Git,
a source checkout, or a separate Python installation. The first install may compile
native dependencies; subsequent upgrades use the same Homebrew workflow.

You need an Apple Account with iCloud Mail and two-factor authentication, an unlocked
native credential store, and internet access to Apple. Install Codex with its CLI on
PATH before using `setup --codex`. Restart Codex after setup.

The formula lives in [MarkUnthank's tap](https://github.com/MarkUnthank/homebrew-tap),
not Homebrew/core. The CLI remains an early release with [these verification limits](../VERIFICATION.md).

## Other platforms: uv or pipx

Install the published wheel directly; no clone needed. Choose one:

```sh
uv tool install https://github.com/MarkUnthank/icloud-agent/releases/download/v0.3.0/icloud_agent-0.3.0-py3-none-any.whl
```

```sh
pipx install https://github.com/MarkUnthank/icloud-agent/releases/download/v0.3.0/icloud_agent-0.3.0-py3-none-any.whl
```

These methods require Python 3.11+ (uv can manage Python for you). Then run the same
`icloud-agent setup --codex` and `icloud-agent auth login` commands. No PyPI or npm
package is published by this project. Avoid installing the CLI through multiple managers.

Linux needs a running Secret Service provider, such as GNOME Keyring, accessible over
the user's D-Bus session. A headless shell without a credential store is unsupported.
Windows uses Credential Manager. These credential-store paths are not yet live-tested.

## Agent setup

`icloud-agent setup --codex` registers local MCP and installs the bundled skill under
`~/.agents/skills/icloud-agent`. Codex reads that shared directory directly. `CODEX_HOME`
still selects the Codex configuration used for MCP registration. Setup preserves
unmanaged registrations/skills with the same name and can update its own integration.
An absolute executable path avoids desktop PATH differences. When using Homebrew,
invoke the command through its stable Homebrew `bin` or `opt` path, not a versioned
Cellar path. Rerun setup after changing installation method.

`icloud-agent setup` without flags exports the bundled desktop plugin and prints its
path. Add `--json` for machine-readable output. On macOS it is `~/Library/Application Support/icloud-agent/plugin/icloud-agent`.
No service is installed. Setup does not authenticate; login happens separately in
your terminal. See [agent setup](clients.md) for other MCP clients.

### Install agent skills

`auth login` finishes with **Install agent skills** and **Finish**
options. Choosing Finish, cancelling, or encountering a skill-installation error leaves
the successful iCloud login saved. The optional prompt is omitted for JSON/piped output.

To install or update skills separately:

```sh
icloud-agent setup --skills
```

The shared skill goes in `~/.agents/skills/icloud-agent`, following the global layout
used by [Skills](https://github.com/vercel-labs/skills). Codex, Cursor, Gemini CLI,
OpenCode, GitHub Copilot, Cline, and other agents that read the shared directory can
use it there. Additional agents start unchecked, with a live selection count above
the picker. Use **Space** to toggle agents and **Enter** to continue. Leave the count
at zero and press **Enter** to skip the extras; the shared skill is still installed.
Supported links include Claude Code, Continue, Goose, OpenClaw, OpenHands, Roo Code,
and Windsurf.

The installer copies the skill bundled with your installed CLI. It runs locally in
Python; it does not invoke `npx`, download skills, or require Node/npm. Additional
agents receive relative symlinks; if symlinks are unavailable, they receive copies.
Use `--copy` to request copies explicitly. Rerun setup after upgrading to refresh copies.

For an agent or script, select targets explicitly; `--json` disables the picker:

```sh
icloud-agent setup --skills --agent claude-code --agent windsurf --json
icloud-agent setup --skills --json
```

The second command installs only the shared skill. `CLAUDE_CONFIG_DIR` and
`XDG_CONFIG_HOME` are respected where applicable. An older icloud-agent-managed Codex
copy is moved to the shared layout so it cannot shadow the updated skill. Unmanaged
files or symlinks with the same name cause a conflict before installation changes them.

For contributors working from source, `python3 install.py --codex --login` remains
available. End users should use a package manager.

## Connect once

Run this yourself in a normal terminal:

```sh
icloud-agent auth login
```

1. Enter your iCloud login email address. The CLI uses it for Mail and Calendar.
2. At `[Press enter to open in browser]`, press Enter to open
   `https://account.apple.com/sign-in`. Sign in, then go to
   **Sign-In and Security → App-Specific Passwords**.
3. Generate a password named `icloud-agent`.
4. Paste the app-specific password into the masked prompt, then press Enter. Trailing
   whitespace copied with the password is removed; a bracketed paste does not submit it.
5. iCloud account addresses and calendars load automatically.
6. Choose enabled senders, then choose the default sender address. Your default can be
   an alias different from your login email.
   If an address is missing, select **Add another address…** in the sender picker.
   **Sender name** is prefilled from your iCloud account when available: Enter accepts
   it, or type a different name. If iCloud supplies no name, enter one.
7. Choose enabled calendars: **arrow keys** move, **Space** toggles, and
   **Enter** saves. Calendars start unchecked; choose those you want the agent to access.
   An empty selection enables none. Ctrl-C cancels without saving changes.
8. Once connected, choose **Install agent skills** or **Finish**.

The CLI validates IMAP and CalDAV before saving credentials. It does not send a test
email; SMTP authentication is checked only during an actual send. It uses your
login email to authenticate. Enabled aliases can be used as senders.
Address discovery reads the account's CalDAV `calendar-user-address-set` using the
same app-specific password. This includes iCloud aliases and custom-domain addresses
on the account tested, but is a calendar identity list, not an SMTP permission check.
Only select addresses you use with iCloud Mail. Apple checks sending permission during
SMTP submission; login does not send a verification message. If Apple omits an address,
you can add it in the picker. No browser session or second password is needed for discovery.

The password is stored in the OS credential store, never in the account JSON or plugin
configuration. Subsequent invocations reuse it. Use `auth login --no-browser` to open
Apple's page yourself. The CLI does not accept password flags or environment variables.

Apple requires two-factor authentication for app-specific passwords. Changing/resetting
your main Apple Account password revokes them, so log in again if that happens.
See [Apple's instructions](https://support.apple.com/en-us/102654).

## Check or change access

```sh
icloud-agent auth configure       # change enabled senders and calendars
icloud-agent auth status          # saved account and credential presence
icloud-agent auth status --check  # live IMAP + CalDAV check
icloud-agent auth logout          # remove the active local credential/config
```

`authenticated_locally:true` means a credential exists; only `--check` tests it against
Apple. One active account is supported. Running login for a different account replaces
the active config and removes the previous account's saved credential from this tool.

`auth configure` reuses the stored password, reloads addresses and calendars, and restores
your choices, including your edited sender name. Run it once if an existing setup has no
sender name saved. Newly discovered addresses and calendars remain unchecked. Sender choices control draft
creation and sending, including previously saved drafts; they do not filter the shared
inbox. `mail senders` lists enabled From addresses and the saved sender name for users and agents.
That name applies to every enabled address; `mail_draft.from_name` can override it for a draft.

Local logout does not revoke the password at Apple. Revoke it at
[account.apple.com](https://account.apple.com/) to invalidate it remotely. Never paste
credentials into a support issue, chat, shell argument, or agent-captured terminal.

## Upgrade

```sh
brew update
brew upgrade MarkUnthank/tap/icloud-agent
icloud-agent setup --codex
```

Upgrading from 0.2.x requires one new `auth login` to explicitly choose access; older
account settings do not silently grant access to every calendar.

Rerun setup to refresh the bundled skill/plugin, then restart your agent. Credentials
and the send journal live outside the package and are retained. For uv/pipx, reinstall
using the new version's wheel URL from [Releases](https://github.com/MarkUnthank/icloud-agent/releases)
and the manager's `--force` option. Review the changelog before updating dependent scripts.

### Switching from the original source installer

Install with Homebrew, then run `"$(brew --prefix)/bin/icloud-agent" setup --codex`.
This updates the managed Codex registration while preserving credentials and journal.
Remove `~/.local/bin/icloud-agent` only if it is the old installer's symlink; otherwise
it may shadow the Homebrew command. You can then remove the old application-data
`runtime` directory. Keep the application-data `plugin` directory and any unrelated files.

## Remove

First run `icloud-agent auth logout` while the executable is still present, then
revoke its app-specific password at Apple if you want remote revocation too.

For an installation made with `--codex`:

```sh
codex mcp remove icloud-agent
```

Remove `~/.agents/skills/icloud-agent` and its links/copies in any additional agents you
selected. For an older installation, the managed skill may still be under
`$CODEX_HOME/skills/icloud-agent` (default `~/.codex/skills/icloud-agent`). If you installed a desktop
plugin separately, uninstall it in that client's plugin manager as well. Finally,
run `brew uninstall icloud-agent`, `pipx uninstall icloud-agent`, or
`uv tool uninstall icloud-agent`, matching your install method. Remove the exported
plugin directory separately. For the source installer, remove its runtime and
`~/.local/bin/icloud-agent` symlink. Delete only paths belonging to this project.

Account metadata and the journal use [platform-specific locations](security.md#local-state).
Logout removes account metadata and the active keychain entry, but intentionally keeps
the send journal. Deleting that journal removes protection against repeated sends of
previously attempted draft IDs. Do not clear it merely to retry a failed send.
