"""Read account identities and calendars using the app-specific password."""

from urllib.parse import unquote, urlsplit

from caldav.elements import cdav, dav

from . import auth, calendar, mail
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
        properties = principal.get_properties([cdav.CalendarUserAddressSet(), dav.DisplayName()])
        try:
            display_name = auth.validate_sender_name(properties.get(dav.DisplayName.tag))
        except AgentError:
            display_name = None
        resources = {
            "addresses": email_identities(properties.get(cdav.CalendarUserAddressSet.tag)),
            "display_name": display_name,
            "calendars": [
                {"id": calendar.trusted_url(str(item.url)), "name": item.name}
                for item in principal.calendars()
            ],
        }
    return resources
