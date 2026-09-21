"""Read calendars and sender identities, using a saved web session when available."""

from urllib.parse import unquote, urlsplit

from caldav.elements import cdav
from keyring.errors import KeyringError

from . import calendar, mail
from .errors import AgentError


def email_identities(values):
    """Ignore principal URLs, UUIDs and malformed mailto values, preserving order."""
    addresses = []
    for value in values or []:
        if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
            continue
        try:
            uri = urlsplit(value)
            if uri.scheme != "mailto" or uri.netloc or uri.query or uri.fragment:
                continue
            address = unquote(uri.path)
            # A property value is one identity, never a header or recipient list.
            if any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in ",;<>" for c in address):
                continue
            address = mail.recipients([address])[0].casefold()
        except (ValueError, AgentError):
            continue
        if address not in addresses:
            addresses.append(address)
    return addresses


def account_resources(account):
    with calendar.connection(account) as client:
        principal = client.principal()
        properties = principal.get_properties([cdav.CalendarUserAddressSet()])
        resources = {
            "addresses": email_identities(properties.get(cdav.CalendarUserAddressSet.tag)),
            "calendars": [
                {"id": calendar.trusted_url(str(item.url)), "name": item.name}
                for item in principal.calendars()
            ],
        }
    from . import web_mail

    try:
        senders = web_mail.optional_senders(account.apple_account)
    except (AgentError, KeyringError):
        senders = None
    if senders is not None:
        resources["addresses"] = senders["addresses"]
        resources["address_source"] = "icloud_mail"
    return resources
