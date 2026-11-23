"""The command: status-report (spec SRG-R12, R13.2, R13.3, R14.1; plan S8)."""

from __future__ import annotations

import pytest
from test_jira_v2 import client_for, jira

from status_report.cli import EXIT_ERROR, EXIT_OK, main


def write_settings(tmp_path, keys=("ALP", "BET")):
    lines = ["teams:"] + [f"  - {{key: {k}, name: Team {k}}}" for k in keys] + ["timezone: UTC"]
    path = tmp_path / "config.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_demo_writes_the_report_without_a_token(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    assert main(["--demo", "--output", str(tmp_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Team status as of 09:42" in out and "🔴 Red" in out
    path = tmp_path / "SRG_2026-12-01_0942.md"
    assert path.is_file() and "**Sample data.**" in path.read_text(encoding="utf-8")


def test_real_read_with_a_fake_jira(tmp_path, capsys):
    client, _ = client_for(jira())
    code = main(["--config", write_settings(tmp_path), "--output", str(tmp_path)], client=client)
    assert code == EXIT_OK
    assert "Team ALP" in capsys.readouterr().out
    assert len(list(tmp_path.glob("SRG_*.md"))) == 1


def test_ac26_unknown_project_stops_at_start(tmp_path, capsys):
    client, _ = client_for(jira())
    code = main(["--config", write_settings(tmp_path, ("ALP", "XYZ")), "--output", str(tmp_path)],
                client=client)
    assert code == EXIT_ERROR
    assert "Project XYZ not found in Jira. Check the key in settings." in capsys.readouterr().err
    assert not list(tmp_path.glob("SRG_*.md"))


def test_ac27_no_token_stops(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "a@b.com")
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    assert main(["--config", write_settings(tmp_path)]) == EXIT_ERROR
    assert "No Jira token found. Add JIRA_API_TOKEN to .env." in capsys.readouterr().err


def test_ac24_empty_settings_stop(tmp_path, capsys):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    assert main(["--config", str(path)]) == EXIT_ERROR
    assert "The settings file has no teams. Add a project key and a team name." in capsys.readouterr().err


def test_help_lists_the_options(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for option in ("--config", "--output", "--demo"):
        assert option in out
    for old in ("--week", "--format", "--project", "--no-ai"):
        assert old not in out


def test_output_folder_is_ignored_by_git():
    from pathlib import Path

    ignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text().splitlines()
    assert "output/" in ignore
