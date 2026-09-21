import io
from contextlib import nullcontext
from types import SimpleNamespace

from caldav.elements import cdav
from rich.console import Console

from icloud_agent import auth, calendar, cli, discovery, terminal, web_mail


def test_identities_accept_aliases_and_custom_domains_but_not_other_uris_or_headers():
    values = [
        "mailto:Primary@icloud.com",
        "mailto:primary@icloud.com",
        "MAILTO:alias@me.com",
        "mailto:hello@custom.example",
        "mailto:plus%2Btag@icloud.com",
        "https://caldav.icloud.com/123/principal/",
        "urn:uuid:123",
        "mailto:bad@icloud.com?bcc=other@example.com",
        "mailto:bad@icloud.com#fragment",
        "mailto:one@icloud.com,two@icloud.com",
        "mailto:Name%20%3Cperson@icloud.com%3E",
        "mailto:bad%0D%0ABcc:other@icloud.com",
        "mailto:bad\r\n@icloud.com",
        "mailto://wrong@icloud.com",
        "mailto:invalid",
        None,
    ]
    assert discovery.email_identities(values) == [
        "primary@icloud.com",
        "alias@me.com",
        "hello@custom.example",
        "plus+tag@icloud.com",
    ]
    assert discovery.email_identities(None) == []


def test_discovery_reads_only_principal_identities_and_calendar_inventory(monkeypatch):
    monkeypatch.setattr(web_mail, "optional_senders", lambda email: None)
    requested = []

    def properties(props):
        requested.extend(prop.tag for prop in props)
        return {cdav.CalendarUserAddressSet.tag: ["mailto:alias@icloud.com"]}

    principal = SimpleNamespace(
        get_properties=properties,
        calendars=lambda: [SimpleNamespace(url="https://caldav.icloud.com/123/home/", name="Home")],
    )
    monkeypatch.setattr(
        calendar,
        "connection",
        lambda account: nullcontext(SimpleNamespace(principal=lambda: principal)),
    )
    assert discovery.account_resources(SimpleNamespace(apple_account="person@icloud.com")) == {
        "addresses": ["alias@icloud.com"],
        "calendars": [{"id": "https://caldav.icloud.com/123/home/", "name": "Home"}],
    }
    assert requested == [cdav.CalendarUserAddressSet.tag]


def test_web_aliases_are_used_in_setup_without_changing_access(monkeypatch):
    account = auth.Account(
        "person@icloud.com", "person@icloud.com", "synthetic", sender_addresses=["old@icloud.com"]
    )
    principal = SimpleNamespace(
        get_properties=lambda props: {
            cdav.CalendarUserAddressSet.tag: ["mailto:calendar-only@icloud.com"]
        },
        calendars=lambda: [],
    )
    monkeypatch.setattr(
        calendar, "connection", lambda a: nullcontext(SimpleNamespace(principal=lambda: principal))
    )
    monkeypatch.setattr(
        web_mail, "optional_senders", lambda email: {"addresses": ["web-alias@icloud.com"]}
    )
    result = discovery.account_resources(account)
    assert result["addresses"] == ["web-alias@icloud.com"]
    assert result["address_source"] == "icloud_mail"
    assert account.sender_addresses == ["old@icloud.com"]


def test_discovered_senders_go_straight_to_picker_and_preserve_default(monkeypatch):
    account = auth.Account(
        "login@example.com",
        "primary@icloud.com",
        "synthetic",
        sender_addresses=["alias@icloud.com"],
        known_sender_addresses=["primary@icloud.com", "alias@icloud.com"],
        default_sender_address="alias@icloud.com",
    )
    offered = []

    def choose(out, label, choices, selected):
        offered.extend(choices)
        assert selected == ["alias@icloud.com"]
        return selected

    monkeypatch.setattr(terminal, "choose", choose)
    monkeypatch.setattr(terminal, "pick_one", lambda out, label, choices, selected: selected)
    output = io.StringIO()
    cli.select_access(
        Console(file=output, theme=terminal.THEME),
        account,
        {
            "addresses": ["PRIMARY@icloud.com", "alias@icloud.com", "new@custom.example"],
            "calendars": [],
        },
    )
    assert [value for _, value in offered] == [
        "primary@icloud.com",
        "alias@icloud.com",
        "new@custom.example",
        "add_address",
    ]
    assert account.sender_addresses == ["alias@icloud.com"]
    assert account.default_sender_address == "alias@icloud.com"
    assert "Additional aliases" not in output.getvalue()


def test_manual_supplement_is_optional_and_must_be_selected(monkeypatch):
    account = auth.Account("login@example.com", "primary@icloud.com", "synthetic")
    calls = []

    def choose(out, label, choices, selected):
        calls.append(choices)
        if len(calls) == 1:
            return ["add_address"]
        assert selected == ["extra@custom.example"]
        return []  # Choosing none must still disable all senders.

    monkeypatch.setattr(terminal, "choose", choose)
    monkeypatch.setattr(terminal, "ask", lambda *args: "extra@custom.example")
    cli.select_access(
        Console(file=io.StringIO(), theme=terminal.THEME),
        account,
        {"addresses": [], "calendars": []},
    )
    assert ("extra@custom.example", "extra@custom.example") in calls[1]
    assert account.sender_addresses == []
    assert account.default_sender_address is None
    assert "add_address" not in account.known_sender_addresses
