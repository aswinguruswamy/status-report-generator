"""Checks that config.yaml has the settings that the rules need."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_config_has_required_sections():
    config = load_config()
    for key in ["jira", "work_types", "priority_map", "blocked_method", "ai", "output"]:
        assert key in config, f"config.yaml has no '{key}' setting"


def test_priority_map_has_p1_to_p5():
    config = load_config()
    assert list(config["priority_map"]) == ["P1", "P2", "P3", "P4", "P5"]


def test_blocked_method_is_valid():
    config = load_config()
    assert config["blocked_method"] in {"status", "flag", "label"}


def test_work_types_exclude_epics_and_subtasks():
    config = load_config()
    assert "Epic" not in config["work_types"]
    assert "Subtask" not in config["work_types"]
