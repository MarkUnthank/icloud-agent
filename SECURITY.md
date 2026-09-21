# Security policy

## Report privately

Please report suspected vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/MarkUnthank/icloud-agent/security/advisories/new).
Avoid filing a public issue with exploit details or private account information.

Include the affected version, impact, minimal reproduction using synthetic data, and
any suggested fix. Never send a real app-specific password, keychain export, account
config, private email body, or calendar payload. If you suspect credential compromise,
revoke that app-specific password at Apple independently of the report.

## Scope and support

The latest code on `main` and latest preview release are the active maintenance targets.
This is an early project without an LTS policy, formal security audit, or guaranteed
response time. Reports are reviewed on a best-effort basis; fixes will be documented
in the changelog and, when appropriate, a GitHub security advisory.

Credential handling, authorization boundaries, untrusted mail/event content, local
state, outbound requests, and unintended writes are relevant areas. See
[security and privacy](docs/security.md) for the intended model and known limitations.

This project cannot guarantee the security of the invoking agent, the local OS account,
or Apple's services. A bug in this connector remains in scope even when it requires
an agent interaction to trigger.
