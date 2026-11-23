"""The README links only to files in the repository and to public pages (SRG-29, D32)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_has_the_required_parts():
    for heading in ("The problem", "Users", "How it works", "Status rules (short form)", "Setup",
                    "How to run", "Config options", "Tests",
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


def test_known_limits_is_the_first_section():
    # Shared item SH5: "Known limits" at the top of every README (SRG v2 spec N8).
    first = next(line for line in README.splitlines() if line.startswith("## "))
    assert first == "## Known limits"


def test_contributing_rules_exist():
    # Shared rules for MCF, SRG and RAID (constitution P9, P12; SH4).
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for words in ("specs/", "test first", "bug", "CI"):
        assert words in text, words


def test_readme_has_no_ai_setup():
    # v2 spec §2: no AI in SRG v2, so no AI key and no AI cost section.
    assert "ANTHROPIC" not in README and "Claude API" not in README
    assert "--no-ai" not in README


def test_readme_links_the_public_demo_under_the_title():
    # SH12: keyless public demo per tool.
    top = README.split("## ", 1)[0]
    assert "[srg-app.streamlit.app](https://srg-app.streamlit.app)" in top


def test_known_limits_name_the_12_weeks_and_the_open_speed_check():
    limits = README.split("## Known limits", 1)[1].split("\n## ", 1)[0]
    assert "needs 12 weeks" in limits
    assert "Not checked yet with real Jira: the speed of 10 teams (target under 15 seconds)" in " ".join(
        limits.split())


def test_ac45_readme_shows_the_3_screenshots():
    # Spec v1.4 SRG-R15.1: screenshots of the table, a team's details and the report.
    for name in ("1-team-table.jpg", "2-team-details.jpg", "3-report.jpg"):
        assert f"](docs/screenshots/{name})" in README
        assert (ROOT / "docs" / "screenshots" / name).is_file(), name
    assert "https://srg-app.streamlit.app" in README
