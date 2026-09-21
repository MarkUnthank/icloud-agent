import argparse
import json
import logging
import re
import sys
import webbrowser
from pathlib import Path

from rich_argparse import RawDescriptionRichHelpFormatter

from . import __version__, auth, calendar, mail, terminal
from .errors import AgentError, error_result
from .operations import OPERATIONS, invoke


def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str))


def check_account(account):
    with mail.connection(account):
        pass
    calendar.calendars(account)


def login(no_browser=False):
    if not sys.stdin.isatty():
        raise AgentError(
            "interactive_login_required",
            "Run icloud-agent auth login directly in your terminal. "
            "Passwords are never accepted as arguments or through chat.",
        )
    out = terminal.console(stderr=True)
    terminal.heading(out, "connect")
    terminal.section(out, "1", "Your account")

    def email(label, default=None):
        while True:
            value = terminal.ask(out, label, default)
            try:
                mail.recipients([value])
                return value
            except AgentError:
                out.print("  Enter a valid email address.", style="failure")

    apple_account = email("Apple Account")
    mail_address = email("iCloud Mail", apple_account)
    out.print()
    terminal.section(out, "2", "App-specific password")
    out.print("  account.apple.com", style="accent")
    out.print("  Sign-In and Security → App-Specific Passwords")
    out.print('  Generate a password named "icloud-agent".', style="muted")
    out.print("  Requires Apple Account two-factor authentication.\n", style="muted")
    if not no_browser:
        webbrowser.open("https://account.apple.com/account/manage")
    out.print("  Saved in your OS credential store.", style="muted")
    while True:
        password = terminal.ask(out, "Password (hidden)", password=True)
        if re.fullmatch(r"[a-zA-Z]{4}(?:-[a-zA-Z]{4}){3}", password):
            break
        out.print("  Use the app-specific password: xxxx-xxxx-xxxx-xxxx", style="failure")
    account = auth.Account(apple_account, mail_address, password)
    out.print()
    with terminal.progress(out, "Checking Mail and Calendar…"):
        check_account(account)
    with auth.operation_lock():
        auth.save(account)
    return {
        "connected": True,
        "mail_address": mail_address,
        "calendar_account": apple_account,
        "credential_storage": "OS credential store",
        "verified": ["IMAP", "CalDAV"],
        "note": "Sending uses the same password; SMTP is checked when sending.",
    }


class HelpFormatter(RawDescriptionRichHelpFormatter):
    styles = {
        **RawDescriptionRichHelpFormatter.styles,
        "argparse.groups": "bold cyan",
        "argparse.prog": "bold cyan",
    }

    def __init__(self, prog):
        super().__init__(prog, console=terminal.console())


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", HelpFormatter)
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Emit JSON, including in a terminal. Automatic when stdout is piped.",
        )

    def error(self, message):
        payload = error_result(AgentError("invalid_arguments", terminal.literal(message)))
        if "--json" in sys.argv or not sys.stdout.isatty():
            emit(payload)
        else:
            from types import SimpleNamespace

            terminal.result(terminal.console(stderr=True), payload, SimpleNamespace())
        self.exit(2)


def parser():
    p = ArgumentParser(
        prog="icloud-agent",
        description="iCloud Mail and Calendar for local agents and your terminal.",
        epilog="Get started: icloud-agent auth login\nAgent setup: icloud-agent setup --codex",
    )
    p.set_defaults(json=False)
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    a = commands.add_parser("auth", help="Save, check, or remove OS-stored credentials.")
    auth_commands = a.add_subparsers(dest="action", required=True)
    auth_commands.add_parser("login", help="Connect your Apple Account.").add_argument(
        "--no-browser", action="store_true"
    )
    auth_commands.add_parser("status", help="Check saved credentials or live access.").add_argument(
        "--check", action="store_true"
    )
    auth_commands.add_parser("logout", help="Remove this tool’s saved credentials.")
    setup_parser = commands.add_parser("setup", help="Install bundled agent integration.")
    setup_parser.add_argument(
        "--codex", action="store_true", help="Register MCP and install the Codex skill."
    )
    commands.add_parser("mcp", help="Run local stdio MCP; no port, tunnel, or background daemon.")
    schema = commands.add_parser(
        "schema", help="Show operations or one operation's JSON input schema."
    )
    schema.add_argument("operation", nargs="?", choices=list(OPERATIONS))
    call = commands.add_parser("call", help="Invoke any named operation with a JSON object.")
    call.add_argument("operation", choices=list(OPERATIONS))
    add_input(call)
    for category in ("mail", "calendar"):
        group = commands.add_parser(category, help=f"Read and manage iCloud {category}.")
        actions = group.add_subparsers(dest="action", required=True)
        for name, operation in OPERATIONS.items():
            prefix = category + "_"
            if not name.startswith(prefix):
                continue
            short = name[len(prefix) :].replace("_", "-")
            action = actions.add_parser(
                short,
                help=operation.description,
                description=operation.description
                + " Input fields: "
                + ", ".join(operation.model.model_fields),
            )
            action.set_defaults(operation=name)
            add_input(action)
    return p


def add_input(p):
    p.add_argument(
        "--input", metavar="FILE", help="JSON input file; '-' reads stdin. Defaults to {}."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input schema without network or credential access.",
    )


def main():
    logging.disable(logging.CRITICAL)
    command_parser = parser()
    if len(sys.argv) == 1:
        command_parser.print_help()
        return
    args = command_parser.parse_args()
    try:
        if args.command == "mcp":
            from .mcp_server import run

            run()
            return
        if args.command == "setup":
            from .setup import setup

            result = {"ok": True, "data": setup(codex=args.codex)}
        elif args.command == "auth":
            if args.action == "login":
                data = login(args.no_browser)
            elif args.action == "logout":
                with auth.operation_lock():
                    data = auth.logout()
            else:
                account = auth.load()
                if args.check:
                    check_account(account)
                data = {
                    "authenticated_locally": True,
                    "mail_address": account.mail_address,
                    "services_checked": args.check,
                }
            result = {"ok": True, "data": data}
        elif args.command == "schema":
            names = [args.operation] if args.operation else OPERATIONS
            result = {
                "ok": True,
                "data": {
                    name: {
                        "description": OPERATIONS[name].description,
                        "write": OPERATIONS[name].write,
                        "input_schema": OPERATIONS[name].model.model_json_schema(),
                    }
                    for name in names
                },
            }
        else:
            raw = (
                (sys.stdin.read() if args.input == "-" else Path(args.input).read_text())
                if args.input
                else "{}"
            )
            result = invoke(args.operation, json.loads(raw), dry_run=args.dry_run)
    except EOFError:
        result = error_result(
            AgentError("cancelled", "Input closed. Run the command again to continue.")
        )
    except KeyboardInterrupt:
        result = error_result(
            AgentError(
                "cancelled",
                "Cancelled. If a write was in progress, read back its state before retrying.",
            )
        )
    except Exception as exc:
        result = error_result(exc)
    if args.json or not sys.stdout.isatty():
        emit(result)
    else:
        terminal.result(terminal.console(stderr=not result["ok"]), result, args)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
