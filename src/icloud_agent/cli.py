import argparse
import json
import logging
import re
import sys
import webbrowser
from pathlib import Path

from rich_argparse import RawDescriptionRichHelpFormatter

from . import __version__, auth, discovery, mail, terminal
from .errors import AgentError, error_result
from .operations import OPERATIONS, invoke


def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str))


def check_account(account):
    with mail.connection(account):
        pass
    return discovery.account_resources(account)


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

    while True:
        value = terminal.ask(out, "iCloud Login Email Address")
        try:
            apple_account = mail.recipients([value])[0]
            break
        except AgentError:
            out.print("  Enter a valid email address.", style="failure")
    mail_address = apple_account
    out.print()
    terminal.section(out, "2", "App-specific password")
    password_url = "https://account.apple.com/sign-in"
    out.print("  " + password_url, style="accent")
    out.print("  Sign-In and Security → App-Specific Passwords")
    out.print('  Generate a password named "icloud-agent".', style="muted")
    out.print("  Two-factor authentication required.\n", style="muted")
    if not no_browser:
        out.print("  [Press enter to open in browser]", style="accent", end="")
        out.input()
        webbrowser.open(password_url)
        out.print()
    while True:
        password = terminal.ask(out, "App-specific password", password=True)
        if re.fullmatch(r"[a-zA-Z]{4}(?:-[a-zA-Z]{4}){3}", password):
            break
        out.print("  Use the app-specific password: xxxx-xxxx-xxxx-xxxx", style="failure")
    account = auth.Account(apple_account, mail_address, password)
    out.print()
    with terminal.progress(out, "Checking Mail and Calendar…"):
        available = check_account(account)
    select_access(out, account, available, first_login=True)
    with auth.operation_lock():
        auth.save(account)
    return {
        "connected": True,
        "mail_address": mail_address,
        "calendar_account": apple_account,
        "sender_addresses": account.sender_addresses,
        "default_sender_address": account.default_sender_address,
        "calendar_ids": account.calendar_ids,
        "credential_storage": "OS credential store",
        "verified": ["IMAP", "CalDAV"],
        "note": "Sending uses the same password; SMTP is checked when sending.",
    }


def select_access(out, account, available, *, first_login=False):
    out.print()
    terminal.section(out, "3" if first_login else "1", "Sender addresses")
    discovered = available["addresses"]
    out.print("  Choose addresses you use with iCloud Mail.", style="muted")
    out.print("  The agent can read the shared inbox for all aliases.\n", style="muted")
    known = list(
        dict.fromkeys(
            item.casefold()
            for item in [account.mail_address, *discovered, *account.known_sender_addresses]
        )
    )
    selected = [account.mail_address.casefold()] if first_login else account.sender_addresses
    while True:
        selected = terminal.choose(
            out,
            "Enable for sending",
            [(x, x) for x in known] + [("Add another address…", "add_address")],
            selected,
        )
        if "add_address" not in selected:
            break
        selected = [item for item in selected if item != "add_address"]
        raw = terminal.ask(out, "Existing iCloud Mail address")
        try:
            address = mail.recipients([raw])[0].casefold()
        except AgentError:
            out.print("  Enter a valid email address.", style="failure")
            continue
        if address not in known:
            known.append(address)
        if address not in selected:
            selected.append(address)
    account.sender_addresses = selected
    account.known_sender_addresses = known
    if account.sender_addresses:
        current_default = account.default_sender_address
        if current_default not in account.sender_addresses:
            current_default = account.sender_addresses[0]
        account.default_sender_address = terminal.pick_one(
            out,
            "Default sender",
            [(address, address) for address in account.sender_addresses],
            current_default,
        )
    else:
        account.default_sender_address = None
    out.print()
    terminal.section(out, "4" if first_login else "2", "Calendars")
    calendars = available["calendars"]
    if calendars:
        names = [str(item["name"] or "Untitled calendar") for item in calendars]
        choices = [
            (name if names.count(name) == 1 else f"{name} · {item['id']}", item["id"])
            for name, item in zip(names, calendars, strict=True)
        ]
        account.calendar_ids = terminal.choose(
            out,
            "Enable calendars",
            choices,
            [] if first_login else account.calendar_ids,
        )
    else:
        account.calendar_ids = []
        out.print("  No calendars found.", style="muted")
    senders, calendars = len(account.sender_addresses), len(account.calendar_ids)
    out.print(
        f"  {senders} sender{'s' if senders != 1 else ''} · "
        f"{calendars} calendar{'s' if calendars != 1 else ''} enabled",
        style="accent",
    )


def configure():
    if not sys.stdin.isatty():
        raise AgentError(
            "interactive_setup_required", "Run icloud-agent auth configure in your terminal."
        )
    with auth.operation_lock():
        account = auth.load()
        original = auth.config_path().read_bytes()
    out = terminal.console(stderr=True)
    terminal.heading(out, "access")
    with terminal.progress(out, "Loading addresses and calendars…"):
        available = discovery.account_resources(account)
    select_access(out, account, available)
    with auth.operation_lock():
        path = auth.config_path()
        if not path.exists() or path.read_bytes() != original:
            raise AgentError(
                "config_changed", "Account settings changed. Run auth configure again."
            )
        auth.save(account)
    return {
        "saved": True,
        "sender_addresses": account.sender_addresses,
        "default_sender_address": account.default_sender_address,
        "calendar_ids": account.calendar_ids,
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
    auth_commands.add_parser("configure", help="Choose enabled senders and calendars.")
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
            elif args.action == "configure":
                data = configure()
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
                    "sender_addresses": account.sender_addresses,
                    "default_sender_address": account.default_sender_address,
                    "calendar_ids": account.calendar_ids,
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
        operation = OPERATIONS.get(getattr(args, "operation", None))
        interrupted_write = operation and operation.write and not args.dry_run
        result = error_result(
            AgentError(
                "cancelled",
                "Check the result before retrying this write."
                if interrupted_write
                else "Cancelled.",
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
