"""Checks for the release (SRG-31, D26, D48)."""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def load_notes():
    spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.notes


def test_changelog_has_a_section_for_the_package_version():
    text = load_notes()(f"v{VERSION}")
    assert "### Stories in this release" in text and "### Known limits" in text
    assert "team-managed" in text


def test_release_notes_stop_at_the_next_version():
    sample = "# Changelog\n\n## v2.0.0 (x)\nnew\n\n## v1.0.0 (y)\nold\n"
    assert load_notes()("v2.0.0", sample) == "new\n"
    with pytest.raises(SystemExit, match="no section"):
        load_notes()("v9.9.9", sample)


def test_each_story_in_the_release_is_in_the_notes():
    text = load_notes()(f"v{VERSION}")
    for key in (13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28):
        assert f"SRG-{key}:" in text


def test_release_workflow_runs_on_version_tags_with_pinned_actions():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text())
    assert workflow[True]["push"]["tags"] == ["v*.*.*"]  # YAML reads "on" as True
    assert workflow["permissions"] == {"contents": "write"}
    for workflow_file in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow_file.read_text().splitlines():
            if "uses:" in line:
                assert re.search(r"@[0-9a-f]{40} # v\d", line), (workflow_file.name, line)
