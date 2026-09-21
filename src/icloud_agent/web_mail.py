"""Read-only iCloud Mail routes verified against Apple's web client."""

from pyicloud.exceptions import PyiCloudServiceNotActivatedException
from requests.exceptions import RequestException

from . import auth, mail, web_session
from .errors import AgentError


def read_json(api, service, path, *, query=None):
    try:
        url = web_session.apple_url(api.get_webservice_url(service).rstrip("/") + path)
    except PyiCloudServiceNotActivatedException:
        raise AgentError(
            "web_mail_unavailable", "This account did not offer the Mail service."
        ) from None
    try:
        response = api.session.request_raw(
            "POST" if query is not None else "GET",
            url,
            params=api.params,
            json=query,
            timeout=30,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            allow_redirects=False,
        )
    except RequestException:
        raise AgentError(
            "apple_connection_failed",
            "Could not reach iCloud Mail. Check your connection and retry.",
        ) from None
    if response.status_code != 200:
        raise AgentError("web_mail_failed", f"iCloud Mail returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError:
        raise AgentError(
            "web_mail_format", "iCloud Mail returned an unexpected response."
        ) from None


def parse_senders(document):
    """Extract only sender identities; never return forwarding, rules, or auto-reply data.

    allowSendFrom is the user's iCloud From-menu preference, not an SMTP permission
    check. Active aliases remain discoverable when unchecked in that menu.
    """
    entries = {}

    def add(identity, domain, kind, active=True):
        name, suffix = identity["emailId"], domain["domain"]
        if (
            not isinstance(name, str)
            or not isinstance(suffix, str)
            or any(c.isspace() or ord(c) < 32 or c in '@,;<>"()' for c in name + suffix)
            or not isinstance(domain["allowSendFrom"], bool)
            or not isinstance(active, bool)
        ):
            raise ValueError()
        address = mail.recipients([name + "@" + suffix])[0].casefold()
        entries[address] = {
            "address": address,
            "kind": kind,
            "active": active,
            "enabled_in_icloud": domain["allowSendFrom"],
        }

    try:
        account = document["account"]
        for domain in account["supportedDomains"]:
            add(account, domain, "primary")
        aliases = account.get("aliases", [])
        custom = account.get("customDomains", [])
        if not isinstance(aliases, list) or not isinstance(custom, list):
            raise ValueError()
        for alias in aliases:
            for domain in alias["supportedDomains"]:
                add(alias, domain, "alias", alias["isActive"])
        for identity in custom:
            add(identity, identity, "custom_domain")
        default = document.get("sharedPreference", {}).get("sendMailFromAddress")
        if default is not None:
            default = mail.recipients([default])[0].casefold()
        addresses = [address for address, entry in entries.items() if entry["active"]]
        return {
            "count": len(addresses),
            "addresses": addresses,
            "default_sender": default if default in addresses else None,
            "identities": list(entries.values()),
        }
    except (KeyError, TypeError, ValueError, AttributeError, AgentError):
        raise AgentError(
            "web_mail_format", "iCloud Mail returned unexpected sender settings."
        ) from None


def senders(api):
    dsid = str(api.params.get("dsid", ""))
    if not dsid.isascii() or not dsid.isdigit():
        raise AgentError("web_mail_format", "iCloud did not return a valid account identifier.")
    document = read_json(
        api,
        "mcc",
        f"/cc/mail/v1/account/{dsid}/preference/web/all"
        "?userEntryPoint=%2Ficloud-agent%2Fsetup&categoryViewEligible=false",
    )
    return parse_senders(document)


def mailboxes(api):
    document = read_json(
        api,
        "mccgateway",
        "/mailws2/v1/geqs/query",
        query={
            "domain": "mailbox",
            "includeLabels": False,
            "predicate": {
                "type": "eq",
                "expression": {"type": "property", "property": "isMboxDeleted"},
                "value": False,
            },
            "properties": ["identifier", "name", "uidValidity"],
            "limit": 100,
        },
    )
    folders = document.get("domainObjects") if isinstance(document, dict) else None
    if not isinstance(folders, list) or any(
        not isinstance(folder, dict)
        or not isinstance(folder.get("identifier"), str)
        or not isinstance(folder.get("name"), str)
        or type(folder.get("uidValidity")) is not int
        for folder in folders
    ):
        raise AgentError("web_mail_format", "iCloud Mail returned an unexpected folder list.")
    return {"count": len(folders), "limit": 100}


def optional_senders(email):
    """Use only this tool's session for the same account; never initiate sign-in."""
    with auth.operation_lock():
        stored = web_session.saved_session(required=False)
        if not stored or stored["email"].casefold() != email.casefold():
            return None
        with web_session.connection(stored["email"], saved=stored) as api:
            if not web_session.is_authenticated(api):
                return None
            result = senders(api)
            web_session.save(api)
            return result
