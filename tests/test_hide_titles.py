"""Option to hide ticket titles from the AI (SRG-26, D25, RAID R04)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

from test_ai import FakeClient as FakeAI
from test_ai import week
from test_cli import REPO_CONFIG, FakeClient, ticket
from test_metrics import CONFIG

from status_report.cli import main
from status_report.config import load_config

HIDDEN = replace(CONFIG, hide_titles_from_ai=True)


def test_default_is_false():
    assert load_config(REPO_CONFIG).hide_titles_from_ai is False


def test_titles_go_to_the_ai_when_the_option_is_false():
    assert "Secret project Falcon" in json.dumps(week(CONFIG))


def test_no_title_goes_to_the_ai_when_the_option_is_true():
    data = week(HIDDEN)
    text = json.dumps(data)
    for title in ("Secret project Falcon", "Closed work", "Green work"):
        assert title not in text
    assert all("title" not in row for row in data["tickets"])
    assert [row["key"] for row in data["tickets"]] == ["SRG-1", "SRG-2"]  # Keys stay


def test_the_report_still_shows_the_titles(tmp_path, monkeypatch):
    monkeypatch.setattr("status_report.cli.load_config", lambda path: HIDDEN)
    answer = {"summary": "The project is Amber. SRG-1 is due soon. Nothing was closed.",
              "next_week": ["Start SRG-1."]}
    ai = FakeAI(answer)
    argv = ["--output", str(tmp_path), "--week", "2026-10-19", "--format", "md"]
    main(argv, client=FakeClient([ticket(title="Confidential title")]),
         today=date(2026, 10, 22), ai_client=ai)
    sent = ai.calls[0]["messages"][0]["content"]
    assert "Confidential title" not in sent
    report = (tmp_path / "SRG-2026-W43.md").read_text()
    assert "Confidential title" in report
