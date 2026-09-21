# Contributing

Thanks for helping improve icloud-agent. Small, well-evidenced changes are easiest to
review. For a new capability or a substantial behavior change, open an issue first so
we can agree on scope. Bugs and documentation corrections can go straight to a PR.

## Your first contribution

Fork the repository, create a focused branch, and open a pull request against `main`.
A draft PR is welcome when you want early feedback. You can work entirely with synthetic
data; an iCloud account is not needed for the test suite. Documentation corrections,
clearer synthetic examples, and regression tests for reproducible bugs are useful places
to start. Check open issues and existing PRs before duplicating work.

Use [good first issue](https://github.com/MarkUnthank/icloud-agent/labels/good%20first%20issue)
for tasks explicitly scoped for newcomers and [help wanted](https://github.com/MarkUnthank/icloud-agent/labels/help%20wanted)
for broader contributions. These labels are applied by maintainers; an empty list simply
means no tasks have been scoped yet. Read [community conduct](CODE_OF_CONDUCT.md) and
[getting help](SUPPORT.md) before posting.

## Development setup

```sh
# Replace YOUR-USERNAME with the owner of your fork.
git clone https://github.com/YOUR-USERNAME/icloud-agent.git
cd icloud-agent
git remote add upstream https://github.com/MarkUnthank/icloud-agent.git
git switch -c describe-your-change
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

### Preview the setup UI

On macOS or Linux, open a separate terminal window and run:

```sh
.venv/bin/python scripts/preview_setup.py app
.venv/bin/python scripts/preview_setup.py web
```

The preview runs the real prompts with example accounts. Network connections,
credential storage, browser launches, and changes to your account settings are
blocked or replaced with fixtures. It clears the preview terminal's scrollback,
so use a dedicated window.

Use `alex@icloud.com`, app password `abcd-efgh-ijkl-mnop`, any example Apple Account
password, and verification code `123456`. Enter advances paused service calls;
Space and arrow keys work as usual in pickers. Ctrl-C exits the final screen.
Run `scripts/preview_setup.py --help` for saved-session, SMS, empty-calendar,
configuration, status, and failure scenarios. These previews verify presentation,
not Apple's live responses.

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

## How changes reach main

`main` requires a pull request, an up-to-date branch, passing Linux checks, and resolved
review conversations. Force-pushes and branch deletion are blocked, including for admins.
Only squash merges are enabled; merged branches are deleted automatically. CODEOWNERS
routes review requests to Mark Unthank. Maintainers decide whether a contribution fits
and review external PRs before merging.

A second-person approval is not a merge requirement while the project has a sole
maintainer, so the maintainer can ship their own PRs after checks pass. External
contributors cannot merge their own changes without repository write access.

Workflows from all outside contributors wait for maintainer approval. This controls
CI usage and lets a maintainer inspect workflow changes before executing them; it is
not a judgment on the contribution. CI uses read-only tokens and Linux runners. Keep
macOS tests local: do not add GitHub-hosted macOS jobs or self-hosted execution of fork
code. Jobs have time limits and obsolete runs are cancelled automatically.

## Releases

Maintainers should use the [release checklist](docs/releasing.md). A green build does
not replace the separate live account acceptance record.
