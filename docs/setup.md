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
uv tool install https://github.com/MarkUnthank/icloud-agent/releases/download/v0.2.0/icloud_agent-0.2.0-py3-none-any.whl
```

```sh
pipx install https://github.com/MarkUnthank/icloud-agent/releases/download/v0.2.0/icloud_agent-0.2.0-py3-none-any.whl
```

These methods require Python 3.11+ (uv can manage Python for you). Then run the same
`icloud-agent setup --codex` and `icloud-agent auth login` commands. No PyPI or npm
package is published by this project. Avoid installing the CLI through multiple managers.

Linux needs a running Secret Service provider, such as GNOME Keyring, accessible over
the user's D-Bus session. A headless shell without a credential store is unsupported.
Windows uses Credential Manager. These credential-store paths are not yet live-tested.

## Agent setup

`icloud-agent setup --codex` registers local MCP and installs the bundled skill under
`$CODEX_HOME/skills/icloud-agent` (default `~/.codex/skills/icloud-agent`). It preserves
unmanaged registrations/skills with the same name and can update its own integration.
An absolute executable path avoids desktop PATH differences. When using Homebrew,
invoke the command through its stable Homebrew `bin` or `opt` path, not a versioned
Cellar path. Rerun setup after changing installation method.

`icloud-agent setup` without flags exports the bundled desktop plugin and prints its
path as JSON. On macOS it is `~/Library/Application Support/icloud-agent/plugin/icloud-agent`.
No service is installed. Setup does not authenticate; login happens separately in
your terminal. See [agent setup](clients.md) for other MCP clients.

For contributors working from source, `python3 install.py --codex --login` remains
available. End users should use a package manager.

## Connect once

Run this yourself in a normal terminal:

```sh
icloud-agent auth login
```

1. In the Apple page that opens, go to **Sign-In and Security → App-Specific Passwords**.
2. Generate a password named `icloud-agent`.
3. In the terminal, enter your Apple Account email.
4. Enter the iCloud Mail address you use to sign into IMAP. This may differ from the
   Apple Account email. The CLI defaults it to the Apple Account email.
5. Paste the app-specific password into the hidden prompt.

The CLI validates IMAP and CalDAV before saving credentials. It does not send a test
email; SMTP authentication is checked only during an actual send. It uses your
configured mail address as the sender. Sending from additional aliases/custom-domain
identities is not implemented as a separate feature.

The password is stored in the OS credential store, never in the account JSON or plugin
configuration. Subsequent invocations reuse it. Use `auth login --no-browser` to open
Apple's page yourself. The CLI does not accept password flags or environment variables.

Apple requires two-factor authentication for app-specific passwords. Changing/resetting
your main Apple Account password revokes them, so log in again if that happens.
See [Apple's instructions](https://support.apple.com/en-us/102654).

## Check or change access

```sh
icloud-agent auth status          # saved account and credential presence
icloud-agent auth status --check  # live IMAP + CalDAV check
icloud-agent auth logout          # remove the active local credential/config
```

`authenticated_locally:true` means a credential exists; only `--check` tests it against
Apple. One active account is supported. Running login for a different account replaces
the active config and removes the previous account's saved credential from this tool.

Local logout does not revoke the password at Apple. Revoke it at
[account.apple.com](https://account.apple.com/) to invalidate it remotely. Never paste
credentials into a support issue, chat, shell argument, or agent-captured terminal.

## Upgrade

```sh
brew update
brew upgrade MarkUnthank/tap/icloud-agent
icloud-agent setup --codex
```

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

Remove the managed `$CODEX_HOME/skills/icloud-agent` (default `~/.codex/skills/icloud-agent`) directory. If you installed a desktop
plugin separately, uninstall it in that client's plugin manager as well. Finally,
run `brew uninstall icloud-agent`, `pipx uninstall icloud-agent`, or
`uv tool uninstall icloud-agent`, matching your install method. Remove the exported
plugin directory separately. For the source installer, remove its runtime and
`~/.local/bin/icloud-agent` symlink. Delete only paths belonging to this project.

Account metadata and the journal use [platform-specific locations](security.md#local-state).
Logout removes account metadata and the active keychain entry, but intentionally keeps
the send journal. Deleting that journal removes protection against repeated sends of
previously attempted draft IDs. Do not clear it merely to retry a failed send.
