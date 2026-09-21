# Contributing

Thanks for helping improve icloud-agent. Small, well-evidenced changes are easiest to
review. For a new capability or a substantial behavior change, open an issue first so
we can agree on scope. Bugs and documentation corrections can go straight to a PR.

## Development setup

```sh
git clone https://github.com/MarkUnthank/icloud-agent.git
cd icloud-agent
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/generate_reference.py --check
.venv/bin/python scripts/check_docs.py
.venv/bin/python -m build
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\ruff.exe`.
Tests use synthetic data and fake Apple transports, plus a real local MCP subprocess.
They do not require an Apple Account or permission to send email.

## Changes that fit this project

- Keep the tool local and on demand; avoid adding a hosted service or a required daemon.
- Prefer the maintained protocol libraries already in use over custom protocol code.
- Add a typed operation to the shared registry so CLI and MCP behavior stay aligned.
- Preserve explicit user intent for writes, opaque IDs, ETag checks, and uncertain-send handling.
- Use meaningful regression tests for behavior, especially mutations and credential storage.
- Keep real inboxes, credentials, addresses, and account identifiers out of fixtures and logs.

After changing schemas, run `python scripts/generate_reference.py` to regenerate the
reference and tool schemas. CI checks for drift. Add/update examples when behavior
changes and record user-visible changes under `Unreleased` in `CHANGELOG.md`.

The project is pre-1.0. We do not preserve backward compatibility by default; document
intentional interface changes and keep the simplest implementation for current needs.

## Pull requests

Explain the user-visible problem and resulting behavior. Include the checks you ran
and any remaining uncertainty. Distinguish a local unit test, MCP transport test, live
Apple readback, and actual agent-client use. Do not call a mocked test a live integration.

Never send a test email or modify a real calendar without the account owner's explicit
intent. Live testing instructions are in [VERIFICATION.md](VERIFICATION.md).

Please be respectful, give specific feedback, and assume good faith. Contributions are
provided under the project's [MIT license](LICENSE). Report security issues using
[SECURITY.md](SECURITY.md), not a public issue. Support and reviews are best effort;
there is no response-time guarantee.

## Releases

Maintainers should use the [release checklist](docs/releasing.md). A green build does
not replace the separate live account acceptance record.
