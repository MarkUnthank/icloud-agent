"""Interactive Apple Account sign-in for the local web-session proof."""

import json
import sys

from rich.text import Text

from . import auth, mail, terminal, web_session
from .errors import AgentError


def login():
    if not sys.stdin.isatty():
        raise AgentError(
            "interactive_login_required", "Run icloud-agent auth web-login in your terminal."
        )
    out = terminal.console(stderr=True)
    terminal.heading(out, "iCloud sign-in")
    with auth.operation_lock():
        stored = web_session.saved_session(required=False)
    default = stored["email"] if stored else None
    if not default and auth.config_path().exists():
        default = json.loads(auth.config_path().read_text()).get("apple_account")
    terminal.section(out, "1", "Your account")
    while True:
        value = terminal.ask(out, "iCloud Login Email Address", default)
        try:
            email = mail.recipients([value])[0].casefold()
            break
        except AgentError:
            out.print("  Enter a valid email address.", style="failure")

    reuse = stored if stored and stored["email"] == email else None
    out.print()
    with web_session.connection(email, saved=reuse) as api:
        reused = False
        if reuse:
            with terminal.progress(out, "Checking saved session…"):
                reused = web_session.is_authenticated(api)
        if not reused:
            password = terminal.password_input(
                out, Text("  Apple Account password › "), strip=False
            )
            if not password:
                raise AgentError("password_required", "Enter your Apple Account password.")
            try:
                api._password_raw = password
                out.print()
                with terminal.progress(out, "Signing in…"):
                    api.authenticate(force_refresh=True)
            finally:
                password = None
                api._password_raw = None
            if api.requires_2fa:
                verify(out, api)
            if not api.is_trusted_session or api.requires_2sa:
                raise AgentError(
                    "web_login_incomplete",
                    "Apple verification did not complete. Run auth web-login again.",
                )
        with auth.operation_lock():
            if web_session.saved_session(required=False) != stored:
                raise AgentError(
                    "web_session_changed",
                    "Another sign-in updated the session. Run auth web-login again.",
                )
            web_session.save(api)
        return {"web_session_saved": True, "email": email, "reused_session": reused}


def verify(out, api):
    out.print()
    terminal.section(out, "2", "Verify your account")
    for attempt in range(3):
        with terminal.progress(out, "Requesting verification…"):
            if not api.request_2fa_code():
                if api.two_factor_delivery_method == "security_key":
                    raise AgentError(
                        "security_key_required",
                        "This account requires a security key; code-based sign-in is unavailable.",
                    )
                raise AgentError(
                    "verification_unavailable", "Apple did not offer device or SMS verification."
                )
        if api.two_factor_delivery_method == "sms":
            out.print("  Enter the code sent to your phone.", style="muted")
        else:
            out.print("  Approve sign-in on your Apple device, then enter its code.", style="muted")
        out.print()
        code = terminal.password_input(out, Text("  Verification code › "))
        out.print()
        try:
            if len(code) == 6 and code.isascii() and code.isdigit():
                with terminal.progress(out, "Verifying…"):
                    valid = api.validate_2fa_code(code)
                if valid and api.is_trusted_session and not api.requires_2fa:
                    return
        finally:
            code = None
        if attempt < 2:
            out.print("  Verification failed. Try a new code.", style="failure")
            out.print()
    raise AgentError("verification_failed", "Apple verification failed. Run auth web-login again.")
