"""The specs and shared docs agree with each other and with the release (audit, 2026-11-23)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = (ROOT / "specs" / "spec.md").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "specs" / "requirements.md").read_text(encoding="utf-8")
CONSTITUTION = (ROOT / "specs" / "constitution.md").read_text(encoding="utf-8")


def change_log_versions(text: str) -> list[tuple[int, ...]]:
    log = text.split("Change log", 1)[1]
    return [tuple(int(n) for n in v.split(".")) for v in re.findall(r"^\| (\d+\.\d+(?:\.\d+)?) \|", log, re.MULTILINE)]


def test_requirements_r15_asks_for_screenshots_not_a_video():
    r15 = next(line for line in REQUIREMENTS.splitlines() if line.startswith("| R15 |"))
    assert "screenshot" in r15.lower() and "video" not in r15.lower()
    assert REQUIREMENTS.startswith("# SRG v2 – Requirements\n\nVersion 1.4 ")
    assert "| 1.4 | 2026-11-23 |" in REQUIREMENTS and "SH-5.5" in REQUIREMENTS


def test_spec_points_to_the_requirements_in_this_repo():
    source = next(line for line in SPEC.splitlines() if line.startswith("Tool: SRG"))
    assert "`specs/requirements.md` v1.4" in source
    assert "R1–R15 and N1–N8" in SPEC
    assert "AC1–AC45" in SPEC.split("## 11. Clarify checklist", 1)[1].split("## 12.", 1)[0]
    acs = re.findall(r"^\| AC(\d+)a? \|", SPEC, re.MULTILINE)
    assert max(int(n) for n in acs) == 45


def test_change_logs_are_in_order():
    for text in (SPEC, REQUIREMENTS, CONSTITUTION):
        versions = change_log_versions(text)
        assert versions == sorted(versions), versions


def test_constitution_is_the_approved_v1_2():
    assert "Version: 1.2 – 2026-11-23" in CONSTITUTION
    sh12 = next(line for line in CONSTITUTION.splitlines() if line.startswith("| SH12 |"))
    assert "screenshots" in sh12 and "video per tool" not in sh12
    assert "Python 3.11–3.14" in CONSTITUTION


def test_contributing_line_is_the_shared_text():
    # The same file in MCF, SRG and RAID.
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert ("4. **Every bug gets a test first** that shows the bug. For AI behaviour (MCF and RAID; "
            "SRG v2 has no AI), also add a sample (eval case).") in text


def test_config_note_says_the_time_zone_default_is_the_computer():
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    note = text.split("\ntimezone:", 1)[0]
    assert "this computer's time zone" in note.split("All settings below are optional.", 1)[1]


def test_ci_comment_matches_the_readme():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "tells users to install Python 3.12" not in workflow
    assert "Python 3.11 or newer" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_devcontainer_uses_the_streamlit_version_of_requirements():
    # Codespaces must run the demo with the same Streamlit as CI and Streamlit Cloud.
    pin = re.search(r"^streamlit==([\d.]+)$", (ROOT / "requirements.txt").read_text(), re.MULTILINE)
    container = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    installs = re.findall(r"pip3 install --user (streamlit[^;\s]*)", container)
    assert pin and installs == [f"streamlit=={pin.group(1)}"]
    assert "--server.enableCORS false --server.enableXsrfProtection false" in container
