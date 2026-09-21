import argparse
import getpass
import json
import logging
import re
import sys
import webbrowser
from pathlib import Path

from . import __version__, auth, calendar, mail
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
            "Run icloud-agent auth login directly in your "
            "terminal. Passwords are never accepted as arguments or through chat.",
        )
    print(
        "Connect iCloud Mail and Calendar once. Your password stays in your OS credential store.",
        file=sys.stderr,
    )
    print(
        "At account.apple.com: Sign-In and Security → App-Specific Passwords → Generate.\n"
        "Name it 'icloud-agent'. Two-factor authentication must be enabled.",
        file=sys.stderr,
    )
    if not no_browser:
        webbrowser.open("https://account.apple.com/account/manage")
    apple_account = input("Apple Account email: ").strip()
    mail_address = input(f"iCloud Mail address [{apple_account}]: ").strip() or apple_account
    mail.recipients([apple_account, mail_address])
    password = getpass.getpass("App-specific password (hidden): ").strip()
    if not re.fullmatch(r"[a-zA-Z]{4}(?:-[a-zA-Z]{4}){3}", password):
        raise AgentError(
            "invalid_password_format",
            "Use Apple's app-specific password in "
            "xxxx-xxxx-xxxx-xxxx format, not your normal Apple Account password.",
        )
    account = auth.Account(apple_account, mail_address, password)
    print("Checking Mail and Calendar…", file=sys.stderr)
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


def parser():
    p = argparse.ArgumentParser(
        description="Local iCloud Mail and Calendar. Output is always JSON."
    )
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    a = commands.add_parser("auth", help="Save, check, or remove OS-stored credentials.")
    auth_commands = a.add_subparsers(dest="action", required=True)
    auth_commands.add_parser("login").add_argument("--no-browser", action="store_true")
    auth_commands.add_parser("status").add_argument("--check", action="store_true")
    auth_commands.add_parser("logout")
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
        group = commands.add_parser(category)
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
    args = parser().parse_args()
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
    except KeyboardInterrupt:
        result = error_result(
            AgentError(
                "cancelled",
                "Cancelled. If a write was in progress, read back its state before retrying.",
            )
        )
    except Exception as exc:
        result = error_result(exc)
    emit(result)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
