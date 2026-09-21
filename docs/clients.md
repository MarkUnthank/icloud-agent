# Connect your agent

[← README](../README.md) · [Setup](setup.md) · [Tool reference](reference.md)

The integration has three entry points: a CLI, a skill that explains how to use it,
and a local stdio MCP process. All use the same account and credentials. Pick one MCP
registration method per client to avoid duplicate tools.

## Codex: recommended

```sh
icloud-agent setup --codex
icloud-agent auth login
```

The setup command registers an absolute command path with `codex mcp add` and installs
the bundled skill into `~/.agents/skills/icloud-agent`, which Codex reads directly.
`CODEX_HOME` controls MCP registration; the skill uses the shared global directory.
Restart Codex or start a fresh local session, then ask it to use iCloud Agent.

```sh
codex mcp get icloud-agent
```

The connection should show `enabled: true`, `transport: stdio`, and `args: mcp`.
The setup command does not change unrelated MCP connections or install a daemon.

## Codex: manual

After installing the CLI with pipx/uv and authenticating in your own terminal:

```sh
# Replace this path with the installed executable.
codex mcp add icloud-agent -- /absolute/path/to/icloud-agent mcp
```

Run `icloud-agent setup --skills` to install the bundled skill. Start a new session
after registration.

## Other stdio MCP clients

Use the client's documented MCP configuration format. Many clients accept:

```json
{
  "mcpServers": {
    "icloud-agent": {
      "command": "/absolute/path/to/icloud-agent",
      "args": ["mcp"]
    }
  }
}
```

The client launches this command as a child process. No URL, port, API key, server
deployment, or tunnel is needed. On Windows, use the installed `.exe` path and JSON
backslash escaping. The client must run under the OS user who saved the credentials.

Do not put the app-specific password into MCP `env`, arguments, or config. Run login
in your own terminal first. An MCP process cannot perform interactive login for you.

Each tool accepts an `arguments` object. For example, a tool call to `mail_search`:

```json
{"arguments":{"folder":"INBOX","unread":true,"limit":10}}
```

Results use `ok` plus `data` or `error`. **Inspect `ok`: an application error can arrive
inside a successful MCP transport response.** Read tools declare `readOnlyHint:true`;
write tools declare it false, with destructive hints on mail moves/calendar deletes.
Annotations assist clients; they are not an authorization firewall. The user's request
and the host's permissions govern execution.

## Skill without MCP

A client that can run local commands may use the companion `SKILL.md` directly.
Choose **Install agent skills** after login, or run `icloud-agent setup --skills`.
The shared copy lives in `~/.agents/skills/icloud-agent`; select any additional agents
in the Space/Enter picker. Their directories link to that copy using the same global
layout as the Skills CLI, without running that CLI or requiring Node/npm.
See [skill installation](setup.md#install-agent-skills) for supported agents and flags.
The skill teaches ID handling, draft hashes, event ETags, and scope boundaries.
A skill alone does not grant filesystem, shell, or iCloud access to a cloud-only client.

## Desktop plugin

Run `icloud-agent setup` to export the plugin bundled with every installation:

```text
.codex-plugin/plugin.json  metadata
.mcp.json                 local process configuration
skills/icloud-agent/      companion skill
```

The exported `.mcp.json` uses the **absolute** installed executable path, so your
desktop client does not need to inherit your shell PATH. The same bundle is available
in the source repository at `src/icloud_agent/resources/plugin`.

Import it using your client's supported local plugin workflow. Plugin packaging and
installation UX vary by client/version. OpenAI documents local marketplace plugins
for Work/Codex in the ChatGPT desktop app; this is not a guarantee of local execution
in every ChatGPT chat. See the [official plugin packaging guide](https://developers.openai.com/plugins/build/plugins).

ChatGPT desktop account/client integration has not been end-to-end verified for this
project. ChatGPT web/cloud/mobile without local execution are outside the scope of this
release. A remote MCP bridge could enable other surfaces, but this project does not
provide one.

## Check the integration

1. Run `icloud-agent auth status --check` in your terminal.
2. Restart your agent and ask it to list iCloud calendars.
3. Confirm it uses `calendar_list` or the matching CLI command.
4. Read one event or message before attempting any authorized write.

A tool count or transport handshake proves discovery, not successful Apple access.
See [verification](../VERIFICATION.md) for separate transport, account, and write checks.
