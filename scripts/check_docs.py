#!/usr/bin/env python3
"""Check local documentation links, release metadata, and example input schemas."""

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from icloud_agent import __version__
from icloud_agent.operations import OPERATIONS

ROOT = Path(__file__).resolve().parents[1]


def links(tokens):
    for token in tokens:
        if token.type == "link_open":
            yield token.attrGet("href")
        elif token.type == "image":
            yield token.attrGet("src")
        elif token.type in ("html_inline", "html_block"):
            yield from re.findall(r'(?:href|src)="([^\"]+)"', token.content)
        if token.children:
            yield from links(token.children)


def main():
    parser = MarkdownIt()
    count = 0
    for path in ROOT.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        for link in links(parser.parse(path.read_text())):
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            assert target.is_relative_to(ROOT), f"Link escapes repo: {path}: {link}"
            assert target.exists(), f"Missing link target: {path}: {link}"
            count += 1
    for file, operation in {
        "mail-search.json": "mail_search",
        "mail-draft.json": "mail_draft",
        "calendar-event.json": "calendar_create",
    }.items():
        OPERATIONS[operation].model.model_validate(
            json.loads((ROOT / "examples" / file).read_text())
        )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    plugin = json.loads((ROOT / "plugins/icloud-agent/.codex-plugin/plugin.json").read_text())
    assert project["version"] == plugin["version"] == __version__, "Release versions differ"
    assert project["requires-python"] == ">=3.11"
    assert "the missing agentic icloud connection" in (ROOT / "README.md").read_text()
    print(f"Verified {count} local documentation links, 3 examples, and release metadata.")


if __name__ == "__main__":
    main()
