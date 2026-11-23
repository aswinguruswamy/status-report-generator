"""Tests for the settings file, config.yaml (v1 SRG-17; v2 spec SRG-R13.1, SRG-R13.2)."""

from pathlib import Path

import pytest

from status_report.config import NO_TEAMS, UNMAPPED, ConfigError, Team, load_config, local_timezone

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
    assert config.teams == (Team("ALP", "Alpha"), Team("BET", "Beta"))
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


# --- Work types (AC 3) ----------------------------------------------------


def test_team_can_change_work_types(tmp_path):
    path = repo_config_with(tmp_path, "work_types: [Story, Task, Bug]", "work_types: [Story, Task, Bug, Defect]")
    assert load_config(path).work_types == ("Story", "Task", "Bug", "Defect")


def test_epic_in_work_types_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "work_types: [Story, Task, Bug]", "work_types: [Story, Epic]")
    with pytest.raises(ConfigError, match="Epics and sub-tasks are not counted"):
        load_config(path)


# --- Clear errors with the line number (AC 5) -----------------------------


def test_invalid_yaml_names_the_line(tmp_path):
    path = write_config(tmp_path, "teams:\n  - key: ALP\n    name: [unclosed\n")
    with pytest.raises(ConfigError, match=r"config\.yaml line \d+: the file is not valid YAML"):
        load_config(path)


def test_missing_file_gives_a_clear_message(tmp_path):
    with pytest.raises(ConfigError, match="was not found. Copy config.yaml"):
        load_config(tmp_path / "config.yaml")


def test_wrong_value_type_names_the_line(tmp_path):
    path = repo_config_with(tmp_path, "amber_window_days: 2", "amber_window_days: two")
    line = line_number_of(path, "amber_window_days: two")
    with pytest.raises(ConfigError, match=f"line {line}: amber_window_days: must be a whole number"):
        load_config(path)


# --- v2: teams and defaults (SRG-R13.1, SRG-R13.2) ---------------------------


def test_ac24_empty_settings_file_stops(tmp_path):
    for text in ("", "# only a comment\n", "teams: []\n", "timezone: UTC\n"):
        with pytest.raises(ConfigError) as error:
            load_config(write_config(tmp_path, text))
        assert str(error.value) == NO_TEAMS
    assert NO_TEAMS == "The settings file has no teams. Add a project key and a team name."


def test_ac25_duplicate_project_key_stops(tmp_path):
    text = "teams:\n  - {key: ALP, name: Alpha}\n  - {key: BET, name: Beta}\n  - {key: alp, name: A2}\n"
    with pytest.raises(ConfigError) as error:
        load_config(write_config(tmp_path, text))
    assert str(error.value) == "Project ALP is listed 2 times. Remove one."


def test_ac1_teams_keep_their_order_and_names(tmp_path):
    text = "teams:\n  - key: ALP\n    name: Alpha\n  - key: BET\n    name: Beta\n"
    assert load_config(write_config(tmp_path, text)).teams == (Team("ALP", "Alpha"), Team("BET", "Beta"))


def test_only_teams_is_required_and_v1_defaults_apply(tmp_path):
    config = load_config(write_config(tmp_path, "teams:\n  - {key: ALP, name: Alpha}\n"))
    assert config.timezone == local_timezone()
    assert config.work_types == ("Story", "Task", "Bug")
    assert config.priority_level("Highest") == "P1" and config.priority_level("Lowest") == "P5"
    assert config.blocked_methods == ("status",)
    assert config.blocked_status_name == "Blocked" and config.blocked_label == "blocked"
    assert config.amber_window_days == 2
    assert config.forecast is True
    assert config.output_folder == "output"


def test_high_priority_is_p1_or_p2_and_unknown_is_not_high():
    config = load_config(REPO_CONFIG)
    assert config.is_high("Highest") and config.is_high("High")
    assert not config.is_high("Medium") and not config.is_high("Urgent") and not config.is_high(None)
    assert "treated as not high priority" in config.unmapped_warning("BET-3", "Urgent")


def test_team_without_a_name_names_the_line(tmp_path):
    path = write_config(tmp_path, "teams:\n  - key: ALP\n    name: Alpha\n  - key: BET\n")
    with pytest.raises(ConfigError, match="line 4: teams: team 2 needs a project key and a team name"):
        load_config(path)


def test_wrong_project_key_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="'AL P' is not a Jira project key"):
        load_config(write_config(tmp_path, "teams:\n  - {key: AL P, name: Alpha}\n"))


def test_wrong_time_zone_is_an_error(tmp_path):
    path = repo_config_with(tmp_path, "timezone: America/Toronto", "timezone: Mars/Base")
    with pytest.raises(ConfigError, match="'Mars/Base' is not a time zone"):
        load_config(path)


def test_ai_and_unknown_settings_are_errors(tmp_path):
    path = repo_config_with(tmp_path, "forecast: true", "forecast: true\nai:\n  enabled: true")
    with pytest.raises(ConfigError, match="'ai' is not a setting.*no AI settings"):
        load_config(path)
    path = repo_config_with(tmp_path, "forecast: true", "forcast: true")
    with pytest.raises(ConfigError, match="'forcast' is not a setting. Remove it or check the spelling"):
        load_config(path)


def test_forecast_must_be_true_or_false(tmp_path):
    path = repo_config_with(tmp_path, "forecast: true", "forecast: maybe")
    with pytest.raises(ConfigError, match="forecast: must be true or false"):
        load_config(path)


def test_local_timezone_uses_tz_variable(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    assert local_timezone() == "Asia/Kolkata"
    monkeypatch.setenv("TZ", "Not/AZone")
    assert local_timezone()  # Falls back to the computer's zone or UTC, never empty
