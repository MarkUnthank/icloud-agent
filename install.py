#!/usr/bin/env python3
"""User-invoked local installer. No root access, service, or credential arguments."""

import argparse
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Install icloud-agent into a private local environment."
    )
    parser.add_argument(
        "--codex", action="store_true", help="Register MCP and install the Codex skill."
    )
    parser.add_argument(
        "--login", action="store_true", help="Run interactive iCloud setup after installation."
    )
    args = parser.parse_args()
    if sys.version_info < (3, 11):  # noqa: UP036 - installer runs before package requirements apply
        parser.error("Python 3.11 or newer is required.")
    root = Path(__file__).resolve().parent
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/icloud-agent"
    elif sys.platform == "win32":
        import os

        base = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
            / "icloud-agent"
        )
    else:
        import os

        base = (
            Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
            / "icloud-agent"
        )
    runtime = base / "runtime"
    bindir = runtime / ("Scripts" if sys.platform == "win32" else "bin")
    executable = bindir / ("icloud-agent.exe" if sys.platform == "win32" else "icloud-agent")
    python = bindir / ("python.exe" if sys.platform == "win32" else "python")
    if args.codex and not shutil.which("codex"):
        parser.error("Install Codex first, or omit --codex.")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    base.chmod(0o700)
    venv.create(runtime, with_pip=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(root)], check=True
    )
    subprocess.run([str(executable), "setup", *(["--codex"] if args.codex else [])], check=True)
    if sys.platform != "win32":
        command = Path.home() / ".local/bin/icloud-agent"
        command.parent.mkdir(parents=True, exist_ok=True)
        if command.is_symlink() and command.resolve() == executable:
            pass
        elif command.exists() or command.is_symlink():
            print(f"Existing command preserved at {command}; use {executable}.")
        else:
            command.symlink_to(executable)
        print(f"CLI: {executable}\nAdd {command.parent} to PATH if it is not already there.")
    else:
        print(f"CLI: {executable}")
    if args.login:
        subprocess.run([str(executable), "auth", "login"], check=True)
    else:
        print(f"Connect iCloud once by running: {str(executable)!r} auth login")


if __name__ == "__main__":
    main()
