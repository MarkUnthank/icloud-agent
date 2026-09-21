# Installation and authentication

[← README](../README.md) · [Troubleshooting](troubleshooting.md)

## Requirements

- Python 3.11 or newer, with `venv` and pip available.
- An Apple Account with iCloud Mail enabled and two-factor authentication.
- A native OS credential store accessible in your current login session.
- Internet access to Apple's IMAP, SMTP, and CalDAV services.
- Codex on PATH if you use the `--codex` installer option.

Check `python3 --version` before starting. On Windows, use `py -3` wherever these
instructions show `python3`. Linux distributions may package `python3-venv` separately.
Linux also needs a running Secret Service provider, such as GNOME Keyring, available
through the user's D-Bus session. A headless shell without a credential store is not
supported. Windows/Linux credential-store behavior is not yet live-tested.

## Recommended: local installer

```sh
git clone https://github.com/MarkUnthank/icloud-agent.git
cd icloud-agent
python3 install.py --codex --login
```

The installer creates a private Python environment, installs this project, registers
its absolute executable path with Codex, copies the companion skill, and runs login.
It does not install a service or modify your shell startup files.

| Option | Effect |
|---|---|
| No options | Install the CLI and make a desktop plugin copy |
| `--codex` | Also register a global Codex MCP connection and install the skill |
| `--login` | Start the interactive authentication flow afterward |

An existing unmanaged skill, MCP entry, or command is preserved. For Codex, install
using the default `~/.codex` location; custom Codex skill directories require manual
skill installation. Restart the agent client after adding tools.

The installer prints its executable and plugin paths. On macOS they are:

```text
~/Library/Application Support/icloud-agent/runtime/bin/icloud-agent
~/Library/Application Support/icloud-agent/plugin/icloud-agent
```

On Linux the runtime is under `$XDG_DATA_HOME/icloud-agent/runtime`, defaulting to
`~/.local/share/icloud-agent/runtime`. On Windows it is under
`%LOCALAPPDATA%\icloud-agent\runtime`, with the executable in `Scripts`.

On macOS/Linux a command symlink is created at `~/.local/bin/icloud-agent`, unless
another command already occupies that path. Add `~/.local/bin` to your shell's PATH
if necessary; the absolute installed path works without doing so.

## Alternative: pipx or uv

From the cloned repository, choose one:

```sh
pipx install .
```

```sh
uv tool install .
```

Then run `icloud-agent auth login` and follow [manual agent setup](clients.md).
These package managers install the CLI; they do not automatically register MCP or
copy the skill. Avoid installing the CLI twice with different methods.

No PyPI package is published by this project. Use this repository or a release wheel.
The source checkout also contains the skill and plugin; the wheel contains the Python
CLI/MCP package, not the desktop plugin bundle.

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

For the local installer, update a clean source checkout and rerun it:

```sh
git pull --ff-only
python3 install.py --codex
```

Credentials and the send journal are outside the runtime and are retained. Restart
your agent afterward. If you installed with pipx or uv, use that tool to reinstall
from the updated checkout instead. This project is pre-1.0; check the changelog for
interface changes before upgrading scripts that depend on it.

## Remove

First run `icloud-agent auth logout` while the executable is still present, then
revoke its app-specific password at Apple if you want remote revocation too.

For an installation made with `--codex`:

```sh
codex mcp remove icloud-agent
```

Remove the managed `~/.codex/skills/icloud-agent` directory. If you installed a desktop
plugin separately, uninstall it in that client's plugin manager as well. Finally,
remove this tool's runtime/plugin directory and its `~/.local/bin/icloud-agent`
symlink, or use `pipx uninstall icloud-agent` / `uv tool uninstall icloud-agent` for
package-manager installs. Delete only paths belonging to this project.

Account metadata and the journal use [platform-specific locations](security.md#local-state).
Logout removes account metadata and the active keychain entry, but intentionally keeps
the send journal. Deleting that journal removes protection against repeated sends of
previously attempted draft IDs. Do not clear it merely to retry a failed send.
