import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock
from platformdirs import user_config_path, user_state_path

from .errors import AgentError

SERVICE = "icloud-agent"


def config_path() -> Path:
    return user_config_path(SERVICE) / "account.json"


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def operation_lock():
    path = private_dir(user_state_path(SERVICE)) / "operations.lock"
    return FileLock(path, timeout=1)


def credential_store():
    # Explicit native backends: never accept a plaintext fallback selected by keyring config.
    if sys.platform == "darwin":
        from keyring.backends.macOS import Keyring
    elif sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring as Keyring
    elif sys.platform.startswith("linux"):
        from keyring.backends.SecretService import Keyring
    else:
        raise AgentError("unsupported_os", "No supported OS credential store is available.")
    return Keyring()


@dataclass
class Account:
    apple_account: str
    mail_address: str
    password: str = field(repr=False)
    sender_addresses: list[str] = field(default_factory=list)
    calendar_ids: list[str] = field(default_factory=list)
    known_sender_addresses: list[str] = field(default_factory=list)


def save(account: Account):
    path = config_path()
    old_account = json.loads(path.read_text())["apple_account"] if path.exists() else None
    private_dir(path.parent)
    store = credential_store()
    previous = store.get_password(SERVICE, account.apple_account)
    store.set_password(SERVICE, account.apple_account, account.password)
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
            temp = Path(f.name)
            json.dump(
                {
                    "apple_account": account.apple_account,
                    "mail_address": account.mail_address,
                    "sender_addresses": account.sender_addresses,
                    "calendar_ids": account.calendar_ids,
                    "known_sender_addresses": account.known_sender_addresses,
                },
                f,
            )
            f.flush()
            os.fsync(f.fileno())
        temp.chmod(0o600)
        temp.replace(path)
    except Exception:
        if previous is None:
            store.delete_password(SERVICE, account.apple_account)
        else:
            store.set_password(SERVICE, account.apple_account, previous)
        raise
    if old_account and old_account != account.apple_account:
        if store.get_password(SERVICE, old_account):
            store.delete_password(SERVICE, old_account)


def load() -> Account:
    path = config_path()
    if not path.exists():
        raise AgentError("not_authenticated", "Run icloud-agent auth login in your terminal once.")
    data = json.loads(path.read_text())
    for key in ("sender_addresses", "calendar_ids", "known_sender_addresses"):
        if (
            key not in data
            or not isinstance(data[key], list)
            or any(not isinstance(value, str) for value in data[key])
        ):
            raise AgentError("setup_required", "Run icloud-agent auth login to choose access.")
    password = credential_store().get_password(SERVICE, data["apple_account"])
    if not password:
        raise AgentError(
            "not_authenticated", "Saved credential is missing. Run icloud-agent auth login."
        )
    return Account(
        data["apple_account"],
        data["mail_address"],
        password,
        data["sender_addresses"],
        data["calendar_ids"],
        data["known_sender_addresses"],
    )


def logout():
    path = config_path()
    if path.exists():
        data = json.loads(path.read_text())
        store = credential_store()
        if store.get_password(SERVICE, data["apple_account"]):
            store.delete_password(SERVICE, data["apple_account"])
        path.unlink()
    return {
        "signed_out": True,
        "note": "Revoke the app-specific password at account.apple.com "
        "if you also want to invalidate it at Apple.",
    }
