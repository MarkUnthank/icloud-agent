"""Local Apple web authentication. Passwords and 2FA codes are never persisted."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from http.cookiejar import Cookie
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAcceptTermsException,
    PyiCloudFailedLoginException,
)
from pyicloud.session import PyiCloudSession
from requests.exceptions import RequestException

from . import auth
from .errors import AgentError

SERVICE = "icloud-agent-web"
SESSION_KEYS = {
    "client_id",
    "account_country",
    "session_id",
    "session_token",
    "trust_token",
    "scnt",
}
APPLE_DOMAINS = ("apple.com", "icloud.com", "apple.com.cn", "icloud.com.cn")


def apple_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        valid = (
            parts.scheme == "https"
            and not parts.username
            and not parts.password
            and parts.port in (None, 443)
            and any(host == domain or host.endswith("." + domain) for domain in APPLE_DOMAINS)
        )
    except ValueError:
        valid = False
    if not valid:
        raise AgentError("invalid_apple_url", "Apple returned an unsupported service address.")
    return url


class MemorySession(PyiCloudSession):
    """Adapt the pinned client: keep its automatic cookie/session writes in memory."""

    def _load_session_data(self):
        self._data = {}

    def _save_session_data(self):
        pass

    def send(self, request, **kwargs):
        # requests calls send again for redirects, so every destination is checked.
        apple_url(request.url)
        kwargs["timeout"] = kwargs.get("timeout") or 30
        kwargs["verify"] = True
        return super().send(request, **kwargs)


def saved_session(*, required=True):
    value = auth.credential_store().get_password(SERVICE, "active")
    if not value:
        if not required:
            return None
        raise AgentError("web_login_required", "Run icloud-agent auth web-login in your terminal.")
    try:
        data = json.loads(value)
        if (
            data["version"] != 1
            or not isinstance(data["email"], str)
            or not isinstance(data["session"], dict)
            or not isinstance(data["cookies"], list)
            or any(not isinstance(v, str) for k, v in data["session"].items() if k in SESSION_KEYS)
            or any(not isinstance(cookie, dict) for cookie in data["cookies"])
        ):
            raise ValueError()
        return data
    except (KeyError, TypeError, ValueError):
        raise AgentError(
            "invalid_web_session", "Run auth web-logout, then auth web-login again."
        ) from None


def cookie_data(cookie):
    return {"rest" if key == "_rest" else key: value for key, value in vars(cookie).items()}


@contextmanager
def connection(email, *, saved=None):
    # PyiCloud currently requires a directory at construction. It contains no secrets:
    # replace the file-persisting session before making any request.
    with TemporaryDirectory(prefix="icloud-agent-web-") as directory:
        client_id = (saved or {}).get("session", {}).get("client_id") or str(uuid4())
        api = PyiCloudService(
            email,
            authenticate=False,
            cookie_directory=directory,
            client_id=client_id,
            with_family=False,
            accept_terms=False,
            verify=True,
        )
        original = api.session
        api._session = MemorySession(
            api,
            client_id=client_id,
            cookie_directory=directory,
            verify=True,
            headers=dict(original.headers),
        )
        original.close()
        try:
            if saved:
                if saved["email"] != email:
                    raise AgentError(
                        "wrong_web_account", "Saved session belongs to another account."
                    )
                api.session.data.update(
                    {k: v for k, v in saved["session"].items() if k in SESSION_KEYS}
                )
                try:
                    for entry in saved["cookies"]:
                        cookie = Cookie(**entry)
                        apple_url("https://" + cookie.domain.lstrip(".") + "/")
                        if not cookie.is_expired():
                            api.session.cookies.set_cookie(cookie)
                except (TypeError, ValueError, AttributeError):
                    raise AgentError(
                        "invalid_web_session", "Run auth web-logout, then auth web-login again."
                    ) from None
            yield api
        except PyiCloudAcceptTermsException:
            raise AgentError(
                "apple_account_action_required",
                "Review Apple's updated terms at https://www.icloud.com, then retry.",
            ) from None
        except PyiCloudFailedLoginException:
            raise AgentError(
                "web_login_failed",
                "Apple could not complete sign-in. Check your password and try auth web-login again.",
            ) from None
        except RequestException:
            raise AgentError(
                "apple_connection_failed", "Could not reach Apple. Check your connection and retry."
            ) from None
        finally:
            api._password_raw = None
            api._clear_trusted_device_bridge_state()
            api.session.close()


def is_authenticated(api):
    status = api.get_auth_status()
    return bool(
        status["authenticated"]
        and status["trusted_session"]
        and not status["requires_2fa"]
        and not status["requires_2sa"]
    )


def save(api):
    if (
        not api.is_trusted_session
        or api.requires_2fa
        or api.requires_2sa
        or not api.session.data.get("session_token")
        or not api.session.cookies.get("X-APPLE-WEBAUTH-TOKEN")
    ):
        raise AgentError(
            "web_login_incomplete", "Complete Apple verification before saving the session."
        )
    data = {
        "version": 1,
        "email": api.account_name,
        "saved_at": datetime.now(UTC).isoformat(),
        "session": {k: v for k, v in api.session.data.items() if k in SESSION_KEYS},
        "cookies": [cookie_data(c) for c in api.session.cookies if not c.is_expired()],
    }
    auth.credential_store().set_password(SERVICE, "active", json.dumps(data))


def status():
    with auth.operation_lock():
        stored = saved_session()
        with connection(stored["email"], saved=stored) as api:
            connected = is_authenticated(api)
            if connected:
                save(api)
            return {"email": stored["email"], "web_session_valid": connected}


def logout():
    with auth.operation_lock():
        store = auth.credential_store()
        if store.get_password(SERVICE, "active"):
            store.delete_password(SERVICE, "active")
    return {"web_session_removed": True}


def probe():
    """Check alias discovery and folders through verified read-only Mail routes."""
    from . import web_mail

    with auth.operation_lock():
        stored = saved_session()
        with connection(stored["email"], saved=stored) as api:
            if not is_authenticated(api):
                raise AgentError("web_session_expired", "Run icloud-agent auth web-login again.")
            results = {}
            for name, read in {
                "aliases": web_mail.senders,
                "mailboxes": web_mail.mailboxes,
            }.items():
                try:
                    results[name] = {"ok": True, **read(api)}
                except AgentError as exc:
                    results[name] = {"ok": False, "code": exc.code, "message": str(exc)}
            save(api)
            return {"web_session_valid": True, "checks": results}
