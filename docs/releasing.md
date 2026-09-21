# Maintainer release checklist

[← Contributing](../CONTRIBUTING.md)

1. Review the changelog, limitations, and verification record. Record only checks actually
   completed; an unverified live integration remains unverified after a release.
2. Confirm the same version in `pyproject.toml`, `src/icloud_agent/__init__.py`, and the
   bundled plugin manifest. Check the README/docs, generated schemas, examples, and artwork.
3. Run all contributor checks, then push and wait for CI on the exact release commit.
4. Build from a clean checkout with `python -m build`. Inspect the source archive for
   the installer, plugin, skill, docs, examples, and license. Inspect/install the wheel
   in an isolated environment and exercise its CLI/MCP entry points.
5. Scan the exact release files for credentials, account data, local paths, caches, and
   generated private state. Compute SHA-256 checksums for release assets.
6. Tag that verified commit and create a GitHub release. Mark previews as prereleases.
   Attach the wheel, source archive, and checksum file with a concise change/verification
   summary. Do not claim PyPI publication unless a separate publication actually occurred.
7. Read back the tag, release commit, attached assets, and public repository visibility.
   Confirm the README header and badges render on GitHub.

This repository currently distributes source and GitHub release artifacts. Registry
publication, release signing, and a hosted docs site are not configured. Do not add
badges implying those services exist.
