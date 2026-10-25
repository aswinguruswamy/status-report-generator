"""The README links only to files in the repository and to public pages (SRG-29, D32)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_has_the_required_parts():
    for heading in ("The problem", "Users", "How it works", "Status rules (short form)", "Setup",
                    "How to run", "Config options", "Cost of the AI summary", "Tests",
                    "Known limits", "Project documents"):
        assert f"## {heading}" in README, heading
    assert "team-managed" in README and "```mermaid" in README


def test_readme_does_not_link_to_the_private_confluence_space():
    assert "atlassian.net" not in README


def test_each_sample_link_works():
    for target in re.findall(r"\]\((examples/[^)]+)\)", README):
        assert (ROOT / target).is_file(), target


def test_each_config_option_in_the_readme_is_in_config_yaml():
    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    for option in re.findall(r"^\| `([a-z_.]+)` \|", README, re.MULTILINE):
        assert option.split(".")[-1] + ":" in config, option


def test_each_document_in_the_docs_index_is_in_docs():
    # D32: the public copies of the Confluence pages.
    names = re.findall(r"`([A-Za-z0-9-]+\.pdf)`", (ROOT / "docs" / "README.md").read_text())
    names += [f"Sprint-{n}-Review.pdf" for n in range(4)]
    for name in names:
        assert (ROOT / "docs" / name).is_file(), name


def test_readme_links_to_files_in_docs():
    for target in re.findall(r"\]\((docs/[^)]+)\)", README):
        assert (ROOT / target).exists(), target
