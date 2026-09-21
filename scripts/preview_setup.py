#!/usr/bin/env python3
"""Run the real setup UI with example accounts and no external side effects.

Run in a dedicated terminal: python scripts/preview_setup.py app
Enter advances a paused service call; normal prompts use their usual keys.
Ctrl-C after a final screen exits. Use synthetic app password abcd-efgh-ijkl-mnop.
Prompts and rendering use production UI code. No network, Keychain, browser launch,
Codex registration, or real account configuration is accessed.
"""

import argparse
import copy
import importlib
import json
import logging
import os
import socket
import sys
import tempfile
import termios
import tty
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import patch

from icloud_agent import agent_skills, auth, cli, discovery
from icloud_agent.errors import AgentError

ADDRESSES = [
    "alex@icloud.com",
    "alex@me.com",
    "hello@icloud.com",
    "hello@me.com",
    "news@icloud.com",
    "receipts@icloud.com",
    "hello@studio.example",
    "alex@studio.example",
    "billing@studio.example",
    "support@studio.example",
]
CALENDARS = [
    {"id": f"https://caldav.icloud.com/100/{name.lower()}/", "name": name}
    for name in ("Personal", "Work", "Projects", "Family")
]


def hold():
    before = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin)
        if os.read(sys.stdin.fileno(), 1) == b"\x03":
            raise KeyboardInterrupt
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, before)


def blocked(*args, **kwargs):
    raise AssertionError("Preview attempted an external side effect")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=[
            "app",
            "app-connected",
            "app-empty",
            "app-fail",
            "configure",
            "configure-conflict",
            "setup",
            "setup-conflict",
        ],
    )
    mode = parser.parse_args().mode
    if not sys.stdin.isatty():
        parser.error("Use a dedicated terminal.")
    logging.disable(logging.CRITICAL)
    account = auth.Account(
        "alex@icloud.com",
        "alex@icloud.com",
        "synthetic-password",
        sender_addresses=[ADDRESSES[0], ADDRESSES[6]],
        calendar_ids=[CALENDARS[0]["id"], CALENDARS[3]["id"]],
        known_sender_addresses=ADDRESSES,
        default_sender_address=ADDRESSES[6],
        sender_name="Alex Example",
    )

    with (
        tempfile.TemporaryDirectory(prefix="icloud-agent-preview-") as directory,
        ExitStack() as stack,
    ):
        config = Path(directory) / "account.json"
        config.write_text(json.dumps({"apple_account": account.apple_account}))

        def resources(*args):
            hold()
            if mode == "app-fail":
                raise AgentError(
                    "connection_failed",
                    "Could not connect to iCloud. Check your connection and app-specific password.",
                )
            if mode == "configure-conflict":
                config.write_text("changed by another setup")
            return {
                "addresses": ADDRESSES,
                "display_name": "Alex Example",
                "calendars": [] if mode == "app-empty" else CALENDARS,
            }

        def setup(**kwargs):
            if mode == "setup-conflict":
                raise AgentError(
                    "setup_conflict",
                    "An unmanaged icloud-agent skill already exists. Rename or remove it before running setup again.",
                )
            return {
                "executable": "/opt/homebrew/bin/icloud-agent",
                "plugin": "~/Library/Application Support/icloud-agent/plugin/icloud-agent",
                "skill": "/Users/alex/.agents/skills/icloud-agent",
                "skills": install_skills(),
                "codex_registered": True,
                "next": "Run icloud-agent auth login",
            }

        def install_skills(agents=(), **kwargs):
            shared = "/Users/alex/.agents/skills/icloud-agent"
            return {
                "skill": shared,
                "agents": list(agents),
                "paths": {
                    shared: "shared",
                    **{
                        f"/Users/alex/{name}/skills/icloud-agent": "symlink"
                        for key, name in (
                            ("claude-code", ".claude"),
                            ("windsurf", ".codeium/windsurf"),
                        )
                        if key in agents
                    },
                },
            }

        for obj, name, replacement in [
            (socket.socket, "connect", blocked),
            (socket.socket, "connect_ex", blocked),
            (socket, "create_connection", blocked),
            (socket, "getaddrinfo", blocked),
            (auth, "credential_store", blocked),
            (auth, "config_path", lambda: config),
            (auth, "operation_lock", nullcontext),
            (auth, "load", lambda: copy.deepcopy(account)),
            (auth, "save", lambda value: None),
            (
                agent_skills,
                "canonical_path",
                lambda: Path("/Users/alex/.agents/skills/icloud-agent"),
            ),
            (
                agent_skills,
                "agent_paths",
                lambda: {
                    key: Path(directory) / key / "skills" for key in agent_skills.LINKED_AGENTS
                },
            ),
            (agent_skills, "install", install_skills),
            (cli, "check_account", resources),
            (discovery, "account_resources", resources),
            (cli.webbrowser, "open", lambda url: True),
            (importlib.import_module("icloud_agent.setup"), "setup", setup),
        ]:
            stack.enter_context(patch.object(obj, name, replacement))
        if mode == "app-connected":
            stack.enter_context(
                patch.object(
                    cli, "login", lambda no_browser=False: {"mail_address": account.mail_address}
                )
            )
        if mode.startswith("app"):
            command = ["auth", "login"]
        elif mode.startswith("configure"):
            command = ["auth", "configure"]
        else:
            command = ["setup", "--codex"]
        print("\033[2J\033[3J\033[H\033]0;icloud-agent · Setup preview\007", end="", flush=True)
        print("\033[32m➜\033[0m  ~ icloud-agent " + " ".join(command))
        sys.argv = ["icloud-agent", *command]
        try:
            cli.main()
        except SystemExit:
            pass
        try:
            hold()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
