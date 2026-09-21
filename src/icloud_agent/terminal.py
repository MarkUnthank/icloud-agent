"""Human presentation only. Protocol data never passes through these renderers."""

import json
import os
import sys
import unicodedata
from contextlib import nullcontext

from rich.console import Console, Group
from rich.json import JSON
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme({"accent": "cyan", "muted": "dim", "success": "green", "failure": "red"})


def console(*, stderr=False):
    return Console(
        file=sys.stderr if stderr else sys.stdout,
        theme=THEME,
        highlight=False,
        markup=False,
        no_color="NO_COLOR" in os.environ,
        color_system=None if "NO_COLOR" in os.environ else "auto",
    )


def literal(value):
    """Keep mail, calendar, paths, and parser input from controlling the terminal."""
    return "".join(
        ch
        for ch in str(value)
        if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"}
    )


def heading(out, title):
    out.print()
    out.print(Text.assemble(("  icloud-agent", "bold accent"), (f"  /  {title}", "muted")))
    out.print()


def section(out, number, title):
    out.print(Text.assemble((f"  {number}  ", "accent"), (title, "bold")))
    out.print()


def ask(out, label, default=None, *, password=False):
    prompt = Text.assemble((f"  {label}", "bold"))
    if default:
        prompt.append(f" [{literal(default)}]", style="muted")
    prompt.append(" › ", style="accent")
    if password:
        import getpass

        out.print(prompt, end="")
        return getpass.getpass("", stream=out.file).strip()
    return out.input(prompt).strip() or default or ""


def progress(out, message):
    if out.is_terminal and not out.is_dumb_terminal and "NO_COLOR" not in os.environ:
        return out.status(Text("  " + message, style="accent"), spinner="dots")
    out.print(Text("  " + message, style="muted"))
    return nullcontext()


def label(key):
    return str(key).replace("_", " ").capitalize()


def value_view(value):
    if isinstance(value, dict):
        table = Table.grid(padding=(0, 2))
        table.add_column(style="muted", max_width=22)
        table.add_column(overflow="fold")
        for key, item in value.items():
            table.add_row(Text(literal(label(key))), value_view(item))
        return table
    if isinstance(value, list):
        if not value:
            return Text("None", style="muted")
        if all(not isinstance(item, (dict, list)) for item in value):
            return Text(literal(", ".join(str(item) for item in value)))
        return Group(*(Panel(value_view(item), border_style="dim", expand=False) for item in value))
    if value is None:
        return Text("—", style="muted")
    if isinstance(value, bool):
        return Text("Yes" if value else "No", style="success" if value else "yellow")
    return Text(literal(value), overflow="fold")


def result(out, payload, args):
    if not payload["ok"]:
        error = payload["error"]
        heading(out, "error")
        out.print(Text("  " + label(error["code"]), style="bold failure"))
        if error.get("message"):
            out.print(Padding(Text(literal(error["message"])), (1, 2, 0, 2)))
        for issue in error.get("issues", []):
            field = ".".join(str(x) for x in issue["field"])
            out.print(Padding(Text(literal(f"{field}: {issue['message']}")), (0, 2)))
        out.print()
        return
    data = payload["data"]
    action = getattr(args, "action", None)
    if args.command == "auth":
        if action == "login":
            out.print()
            out.print(Text("  Connected to iCloud", style="bold success"))
            out.print(Text("  " + literal(data["mail_address"]), style="muted"))
            out.print("\n  Mail and Calendar verified. SMTP is checked when you send.")
            out.print(
                Text("  Next: restart your agent, or run icloud-agent mail search", style="muted")
            )
            out.print()
            return
        title = "account"
    elif args.command == "setup":
        title = "agent setup"
    else:
        title = getattr(args, "operation", None) or args.command
        title = title.replace("_", " ")
    heading(out, title)
    if args.command == "schema":
        out.print(JSON(json.dumps(data, ensure_ascii=True, default=str)))
    elif args.command == "setup":
        if data["codex_registered"]:
            out.print(Text("  Codex ready", style="bold success"))
            out.print()
        out.print(
            Padding(
                value_view(
                    {
                        k: v
                        for k, v in data.items()
                        if k not in {"next", "codex_registered"} and v is not None
                    }
                ),
                (0, 2),
            )
        )
        out.print("\n  Next: icloud-agent auth login")
        out.print(Text("  Restart your agent to load the tools.", style="muted"))
    else:
        out.print(Padding(value_view(data), (0, 2)))
    out.print()


def choose(out, title, choices, selected):
    """Use the same stderr surface as login; never write prompt UI to JSON stdout."""
    import questionary
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.output.defaults import create_output

    return questionary.checkbox(
        title,
        choices=[
            questionary.Choice(literal(name), value=value, checked=value in selected)
            for name, value in choices
        ],
        instruction="(↑↓ move · Space toggle · Enter save)",
        style=questionary.Style(
            [
                ("qmark", "fg:ansicyan"),
                ("question", "bold"),
                ("answer", "fg:ansicyan bold"),
                ("pointer", "fg:ansicyan bold"),
                ("highlighted", "fg:ansicyan"),
                ("selected", "fg:ansicyan"),
            ]
        )
        if "NO_COLOR" not in os.environ
        else questionary.Style([]),
        output=create_output(stdout=out.file),
        color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
    ).unsafe_ask()


def pick_one(out, title, choices, selected):
    """Choose one value while keeping all prompt output away from JSON stdout."""
    import questionary
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.output.defaults import create_output

    return questionary.select(
        title,
        choices=[questionary.Choice(literal(name), value=value) for name, value in choices],
        default=selected,
        instruction="(↑↓ move · Enter select)",
        style=questionary.Style(
            [
                ("qmark", "fg:ansicyan"),
                ("question", "bold"),
                ("answer", "fg:ansicyan bold"),
                ("pointer", "fg:ansicyan bold"),
                ("highlighted", "fg:ansicyan"),
            ]
        )
        if "NO_COLOR" not in os.environ
        else questionary.Style([]),
        output=create_output(stdout=out.file),
        color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
    ).unsafe_ask()
