"""Tests for config.yaml loading and checks (SRG-17)."""

from pathlib import Path

import pytest

from status_report.config import UNMAPPED, ConfigError, load_config

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def write_config(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def repo_config_with(tmp_path, old, new):
    text = REPO_CONFIG.read_text(encoding="utf-8")
    assert old in text, f"test setup: '{old}' is not in config.yaml"
    return write_config(tmp_path, text.replace(old, new, 1))


def line_number_of(path, fragment):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if fragment in line:
            return number
    raise AssertionError(f"'{fragment}' not found")


# --- The repository config.yaml is valid --------------------------------


def test_repository_config_loads():
    config = load_config(REPO_CONFIG)
    assert config.project_key == "SRG"
    assert config.work_types == ("Story", "Task", "Bug")
    assert config.blocked_methods == ("status",)


# --- Priority map (AC 1 and AC 4) ----------------------------------------


def test_default_priority_map_is_highest_p1_to_lowest_p5():
    config = load_config(REPO_CONFIG)
    expected = {"Highest": "P1", "High": "P2", "Medium": "P3", "Low": "P4", "Lowest": "P5"}
    for name, level in expected.items():
        assert config.priority_level(name) == level


def test_priority_names_ignore_case_and_spaces():
    config = load_config(REPO_CONFIG)
    assert config.priority_level("  highest ") == "P1"


def test_team_can_map_more_than_one_name_to_a_level(tmp_path):
    path = repo_config_with(tmp_path, "P1: Highest", "P1: [Highest, Blocker]")
    config = load_config(path)
    assert config.priority_level("Blocker") == "P1"
    assert config.priority_level("Highest") == "P1"


def test_unknown_priority_goes_to_unmapped_and_is_not_lost():
    config = load_config(REPO_CONFIG)
    assert config.priority_level("Critical") == UNMAPPED
    assert config.priority_level(None) == UNMAPPED


def test_unmapped_warning_names_the_ticket_and_the_priority():
    config = load_config(REPO_CONFIG)
    message = config.unmapped_warning("SRG-99", "Critical")
    assert "SRG-99" in message
    assert "Critical" in message
    assert UNMAPPED in message


def test_same_jira_name_on_two_levels_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "P2: High", "P2: Highest")
    with pytest.raises(ConfigError, match="also in P1"):
        load_config(path)


def test_missing_priority_level_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "  P5: Lowest\n", "")
    with pytest.raises(ConfigError, match=r"priority_map\.P5: this setting is missing"):
        load_config(path)


def test_wrong_priority_level_name_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "P5: Lowest", "P6: Lowest")
    with pytest.raises(ConfigError, match="'P6' is not valid"):
        load_config(path)


# --- Blocked method (AC 2) ------------------------------------------------


def test_more_than_one_blocked_method(tmp_path):
    path = repo_config_with(tmp_path, "blocked_method: [status]", "blocked_method: [status, flag, label]")
    config = load_config(path)
    assert config.blocked_methods == ("status", "flag", "label")


def test_single_blocked_method_as_text(tmp_path):
    path = repo_config_with(tmp_path, "blocked_method: [status]", "blocked_method: flag")
    assert load_config(path).blocked_methods == ("flag",)


def test_wrong_blocked_method_names_the_line(tmp_path):
    path = repo_config_with(tmp_path, "blocked_method: [status]", "blocked_method: [flagg]")
    line = line_number_of(path, "blocked_method: [flagg]")
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert f"line {line}" in str(error.value)
    assert "'flagg' is not valid. Use status, flag, or label." in str(error.value)


def test_label_method_needs_a_label_name(tmp_path):
    path = repo_config_with(tmp_path, "blocked_method: [status]", "blocked_method: [label]")
    path.write_text(path.read_text().replace("blocked_label: blocked\n", ""), encoding="utf-8")
    with pytest.raises(ConfigError, match="blocked_label: this setting is missing"):
        load_config(path)


# --- Work types (AC 3) ----------------------------------------------------


def test_team_can_change_work_types(tmp_path):
    path = repo_config_with(tmp_path, "  - Bug\n", "  - Bug\n  - Defect\n")
    assert load_config(path).work_types == ("Story", "Task", "Bug", "Defect")


def test_epic_in_work_types_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "  - Bug\n", "  - Bug\n  - Epic\n")
    with pytest.raises(ConfigError, match="D23"):
        load_config(path)


# --- Clear errors with the line number (AC 5) -----------------------------


def test_invalid_yaml_names_the_line(tmp_path):
    path = write_config(tmp_path, "jira:\n  project_key: SRG\n  timezone: [unclosed\n")
    with pytest.raises(ConfigError, match=r"config\.yaml line \d+: the file is not valid YAML"):
        load_config(path)


def test_missing_file_gives_a_clear_message(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        load_config(tmp_path / "config.yaml")


def test_wrong_value_type_names_the_line(tmp_path):
    path = repo_config_with(tmp_path, "amber_window_days: 2", "amber_window_days: two")
    line = line_number_of(path, "amber_window_days: two")
    with pytest.raises(ConfigError, match=f"line {line}: ticket_status.amber_window_days"):
        load_config(path)


def test_wrong_true_false_value(tmp_path):
    path = repo_config_with(tmp_path, "hide_titles_from_ai: false", "hide_titles_from_ai: maybe")
    with pytest.raises(ConfigError, match="must be true or false"):
        load_config(path)


def test_wrong_output_format(tmp_path):
    path = repo_config_with(tmp_path, "formats: [markdown, html]", "formats: [markdown, pdf]")
    with pytest.raises(ConfigError, match="'pdf' is not valid"):
        load_config(path)
