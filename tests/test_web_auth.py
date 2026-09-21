import io
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from pyicloud.exceptions import PyiCloudFailedLoginException
from requests.adapters import BaseAdapter
from requests.cookies import RequestsCookieJar, create_cookie
from rich.console import Console

from icloud_agent import auth, cli, terminal, web_login, web_mail, web_session
from icloud_agent.errors import AgentError


class Store:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, value):
        self.values[service, username] = value

    def delete_password(self, service, username):
        del self.values[service, username]


@pytest.fixture
def store(monkeypatch, tmp_path):
    result = Store()
    monkeypatch.setattr(auth, "credential_store", lambda: result)
    monkeypatch.setattr(auth, "operation_lock", nullcontext)
    monkeypatch.setattr(auth, "config_path", lambda: tmp_path / "account.json")
    return result


def authenticated_api():
    cookies = RequestsCookieJar()
    cookies.set_cookie(
        create_cookie(
            "X-APPLE-WEBAUTH-TOKEN", "synthetic-cookie", domain=".icloud.com", secure=True
        )
    )
    return SimpleNamespace(
        account_name="person@icloud.com",
        is_trusted_session=True,
        requires_2fa=False,
        requires_2sa=False,
        session=SimpleNamespace(
            data={"client_id": "test-client", "session_token": "synthetic-session"}, cookies=cookies
        ),
    )


def test_session_round_trip_uses_only_native_store_and_never_password(store):
    api = authenticated_api()
    api._password_raw = "synthetic-password"
    api.session.data.update({"password": api._password_raw, "securityCode": "123456"})
    api.session.cookies.set_cookie(
        create_cookie("expired", "discard", domain=".icloud.com", expires=1)
    )
    web_session.save(api)
    assert list(store.values) == [("icloud-agent-web", "active")]
    document = store.get_password("icloud-agent-web", "active")
    assert "synthetic-password" not in document and "123456" not in document
    saved = web_session.saved_session()
    assert len(saved["cookies"]) == 1
    with web_session.connection(saved["email"], saved=saved) as restored:
        assert restored._password_raw is None
        assert restored.session.data["session_token"] == "synthetic-session"
        cookie = next(iter(restored.session.cookies))
        assert cookie.value == "synthetic-cookie" and cookie.secure
        assert cookie.domain == ".icloud.com" and cookie.path == "/"
        assert not list(Path(restored.session._cookie_directory).iterdir())
    assert not Path(restored.session._cookie_directory).exists()


@pytest.mark.parametrize(
    "field,value", [("requires_2fa", True), ("requires_2sa", True), ("is_trusted_session", False)]
)
def test_incomplete_verification_cannot_save(store, field, value):
    api = authenticated_api()
    setattr(api, field, value)
    with pytest.raises(AgentError, match="Complete Apple verification"):
        web_session.save(api)
    assert not store.values


def test_incomplete_session_cannot_save(store):
    api = authenticated_api()
    api.session.cookies.clear()
    with pytest.raises(AgentError):
        web_session.save(api)
    assert not store.values


def test_logout_removes_only_our_web_session(store):
    store.set_password(auth.SERVICE, "person@icloud.com", "synthetic-app-password")
    web_session.save(authenticated_api())
    web_session.logout()
    assert store.values == {(auth.SERVICE, "person@icloud.com"): "synthetic-app-password"}
    assert web_session.saved_session(required=False) is None


@pytest.mark.parametrize(
    "value",
    [
        "not json",
        "[]",
        '{"version": 2}',
        '{"version": 1, "email": "a", "session": {"client_id": []}, "cookies": []}',
    ],
)
def test_invalid_saved_session_is_actionable(store, value):
    store.set_password(web_session.SERVICE, "active", value)
    with pytest.raises(AgentError, match="web-logout"):
        web_session.saved_session()


@pytest.mark.parametrize(
    "url",
    [
        "http://icloud.com/",
        "https://icloud.com.evil.example/",
        "https://user:secret@icloud.com/",
        "https://icloud.com:8443/",
        "https://icloud.com:bad/",
    ],
)
def test_session_rejects_non_apple_destinations(url):
    with pytest.raises(AgentError):
        web_session.apple_url(url)


class Adapter(BaseAdapter):
    def __init__(self, redirect=False):
        self.calls = []
        self.redirect = redirect

    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = 302 if self.redirect else 200
        response._content = b"{}"
        response.headers = requests.structures.CaseInsensitiveDict(
            {
                "Location": "https://outside.example/",
                "Content-Type": "application/json",
            }
        )
        return response

    def close(self):
        pass


def test_requests_keep_secrets_off_disk_and_require_tls():
    with web_session.connection("person@icloud.com") as api:
        adapter = Adapter()
        api.session.mount("https://", adapter)
        api.session.data["session_token"] = "synthetic-session"
        api.session.get("https://setup.icloud.com/validate", verify=False)
        assert adapter.calls[0][1]["verify"] is True
        assert adapter.calls[0][1]["timeout"] == 30
        assert not list(Path(api.session._cookie_directory).iterdir())


def test_redirect_cannot_forward_authentication_to_another_site():
    with web_session.connection("person@icloud.com") as api:
        adapter = Adapter(redirect=True)
        api.session.mount("https://", adapter)
        with pytest.raises(AgentError):
            api.session.get("https://setup.icloud.com/validate")
        assert len(adapter.calls) == 1


def test_connection_cleans_password_and_bridge_on_failure(monkeypatch):
    closed = []
    with pytest.raises(AgentError) as error:
        with web_session.connection("person@icloud.com") as api:
            monkeypatch.setattr(
                api, "_clear_trusted_device_bridge_state", lambda: closed.append(True)
            )
            api._password_raw = "synthetic-secret"
            raise PyiCloudFailedLoginException("raw body synthetic-secret")
    assert api._password_raw is None and closed
    assert "synthetic-secret" not in str(error.value)


def sender_preferences():
    return {
        "account": {
            "emailId": "inbox",
            "supportedDomains": [{"domain": "icloud.com", "allowSendFrom": False}],
            "aliases": [
                {
                    "emailId": "News",
                    "supportedDomains": [
                        {"domain": "icloud.com", "allowSendFrom": True},
                        {"domain": "me.com", "allowSendFrom": False},
                    ],
                    "isActive": True,
                },
                {
                    "emailId": "retired",
                    "supportedDomains": [{"domain": "icloud.com", "allowSendFrom": False}],
                    "isActive": False,
                },
            ],
            "customDomains": [
                {"emailId": "hello", "domain": "custom.example", "allowSendFrom": True}
            ],
        },
        "sharedPreference": {"sendMailFromAddress": "News@icloud.com"},
        "serverPreference": {
            "forwardEmailAddress": "private@example.com",
            "autoReplyMessage": "private-text",
        },
        "rules": [{"body": "private-rule"}],
    }


def test_senders_expand_domains_keep_icloud_flags_and_exclude_inactive_aliases():
    result = web_mail.parse_senders(sender_preferences())
    assert result["addresses"] == [
        "inbox@icloud.com",
        "news@icloud.com",
        "news@me.com",
        "hello@custom.example",
    ]
    assert result["count"] == 4 and result["default_sender"] == "news@icloud.com"
    assert result["identities"][0]["enabled_in_icloud"] is False
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "document",
    [{"error": "private-error"}, {"account": None}, {"account": {"supportedDomains": ["wrong"]}}],
)
def test_sender_error_responses_are_not_reported_as_success(document):
    with pytest.raises(AgentError) as error:
        web_mail.parse_senders(document)
    assert error.value.code == "web_mail_format"
    assert "private" not in str(error.value)


@pytest.mark.parametrize("bad_name", ["bad\r\nBcc:other", "Name <email>", "a,b", "name@icloud.com"])
def test_sender_fields_cannot_inject_headers_or_extra_addresses(bad_name):
    document = sender_preferences()
    document["account"]["emailId"] = bad_name
    with pytest.raises(AgentError):
        web_mail.parse_senders(document)


def test_probe_uses_only_known_read_routes_and_omits_unrelated_preferences(store, monkeypatch):
    api = authenticated_api()
    api.params = {"dsid": "123"}
    api.get_webservice_url = lambda name: f"https://{name}.icloud.com"
    api.get_auth_status = lambda: {
        "authenticated": True,
        "trusted_session": True,
        "requires_2fa": False,
        "requires_2sa": False,
    }
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        document = (
            sender_preferences()
            if method == "GET"
            else {"domainObjects": [{"identifier": "1", "name": "INBOX", "uidValidity": 1}]}
        )
        return SimpleNamespace(status_code=200, json=lambda: document)

    api.session.request_raw = request
    web_session.save(api)
    monkeypatch.setattr(web_session, "connection", lambda *a, **kw: nullcontext(api))
    result = web_session.probe()
    assert all(check["ok"] for check in result["checks"].values())
    assert "private@example.com" not in json.dumps(result)
    assert result["checks"]["aliases"]["count"] == 4
    assert result["checks"]["mailboxes"]["count"] == 1
    assert [(method, url) for method, url, _ in calls] == [
        (
            "GET",
            "https://mcc.icloud.com/cc/mail/v1/account/123/preference/web/all?userEntryPoint=%2Ficloud-agent%2Fsetup&categoryViewEligible=false",
        ),
        ("POST", "https://mccgateway.icloud.com/mailws2/v1/geqs/query"),
    ]
    assert calls[1][2]["json"]["domain"] == "mailbox"
    assert calls[1][2]["json"]["properties"] == ["identifier", "name", "uidValidity"]
    assert all(not kwargs["allow_redirects"] for _, _, kwargs in calls)


def test_optional_discovery_never_uses_another_accounts_session(store, monkeypatch):
    web_session.save(authenticated_api())
    monkeypatch.setattr(
        web_session, "connection", lambda *a, **kw: pytest.fail("Wrong account connected")
    )
    assert web_mail.optional_senders("someone-else@icloud.com") is None


def test_folder_error_payload_is_rejected(monkeypatch):
    monkeypatch.setattr(web_mail, "read_json", lambda *a, **kw: {"error": "private-error"})
    with pytest.raises(AgentError) as error:
        web_mail.mailboxes(object())
    assert error.value.code == "web_mail_format"


def interactive_login(monkeypatch):
    api = authenticated_api()
    api.is_trusted_session = False
    api.requires_2fa = True
    api.two_factor_delivery_method = "trusted_device"
    api.request_2fa_code = lambda: True
    seen = []

    def authenticate(**kwargs):
        seen.append(api._password_raw)

    def validate(code):
        assert api._password_raw is None
        seen.append(code)
        api.is_trusted_session = True
        api.requires_2fa = False
        return True

    api.authenticate = authenticate
    api.validate_2fa_code = validate
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        terminal, "console", lambda **kw: Console(file=output, theme=terminal.THEME)
    )
    monkeypatch.setattr(terminal, "ask", lambda *a: "person@icloud.com")
    entries = iter(["  synthetic-password  ", "123456"])
    monkeypatch.setattr(terminal, "password_input", lambda *a, **kw: next(entries))
    monkeypatch.setattr(web_session, "connection", lambda *a, **kw: nullcontext(api))
    return api, seen, output


def test_interactive_login_handles_2fa_and_never_saves_or_prints_password_or_code(
    store, monkeypatch
):
    api, seen, output = interactive_login(monkeypatch)
    result = web_login.login()
    assert result["web_session_saved"] and not result["reused_session"]
    assert seen == ["  synthetic-password  ", "123456"]
    assert api._password_raw is None
    for secret in seen:
        assert secret not in output.getvalue() + json.dumps(
            store.values.get((web_session.SERVICE, "active"))
        )


def test_valid_session_reuses_without_password_or_2fa(store, monkeypatch):
    api, seen, output = interactive_login(monkeypatch)
    api.is_trusted_session, api.requires_2fa = True, False
    web_session.save(api)
    monkeypatch.setattr(web_session, "is_authenticated", lambda api: True)
    result = web_login.login()
    assert result["reused_session"] and not seen


def test_expired_session_prompts_for_password_and_verification(store, monkeypatch):
    api, seen, output = interactive_login(monkeypatch)
    web_session.save(authenticated_api())
    monkeypatch.setattr(web_session, "is_authenticated", lambda api: False)
    result = web_login.login()
    assert not result["reused_session"]
    assert seen == ["  synthetic-password  ", "123456"]


@pytest.mark.parametrize(
    "method,error_code",
    [("security_key", "security_key_required"), ("unknown", "verification_unavailable")],
)
def test_unavailable_verification_does_not_save(store, monkeypatch, method, error_code):
    api, seen, output = interactive_login(monkeypatch)
    api.two_factor_delivery_method = method
    api.request_2fa_code = lambda: False
    with pytest.raises(AgentError) as error:
        web_login.login()
    assert error.value.code == error_code
    assert not store.values


def test_failed_login_does_not_replace_an_existing_session(store, monkeypatch):
    api, seen, output = interactive_login(monkeypatch)
    web_session.save(authenticated_api())
    previous = store.values.copy()
    monkeypatch.setattr(web_session, "is_authenticated", lambda api: False)

    def fail(**kwargs):
        raise AgentError("web_login_failed", "Synthetic failure")

    api.authenticate = fail
    with pytest.raises(AgentError):
        web_login.login()
    assert store.values == previous
    assert api._password_raw is None


def test_failed_2fa_never_replaces_saved_session(store, monkeypatch):
    api, seen, output = interactive_login(monkeypatch)
    entries = iter(["synthetic-password", "111111", "222222", "333333"])
    monkeypatch.setattr(terminal, "password_input", lambda *a, **kw: next(entries))
    api.validate_2fa_code = lambda code: False
    with pytest.raises(AgentError) as error:
        web_login.login()
    assert error.value.code == "verification_failed"
    assert not store.values
    assert api._password_raw is None


def test_cancel_clears_password_and_preserves_existing_credentials(store, monkeypatch):
    api, seen, output = interactive_login(monkeypatch)
    store.set_password(auth.SERVICE, "person@icloud.com", "synthetic-app-password")

    def cancel(**kwargs):
        raise KeyboardInterrupt

    api.authenticate = cancel
    with pytest.raises(KeyboardInterrupt):
        web_login.login()
    assert api._password_raw is None
    assert store.values == {(auth.SERVICE, "person@icloud.com"): "synthetic-app-password"}


def test_piped_web_password_is_rejected_before_loading_credentials(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("synthetic-secret"))
    monkeypatch.setattr(auth, "credential_store", lambda: pytest.fail("Credential access"))
    with pytest.raises(AgentError) as error:
        web_login.login()
    assert error.value.code == "interactive_login_required"


def test_cli_never_displays_raw_provider_exception(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["icloud-agent", "auth", "web-status", "--json"])
    monkeypatch.setattr(
        web_session, "status", lambda: (_ for _ in ()).throw(RuntimeError("synthetic-secret"))
    )
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    with pytest.raises(SystemExit):
        cli.main()
    assert "synthetic-secret" not in output.getvalue()
