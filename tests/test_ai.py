"""Tests for the AI summary guardrails (SRG-23, D02, D03, D25, D28).

No test calls the real Claude API. A fake client gives the answers.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
from test_metrics import CONFIG, at, change, ticket

from status_report.ai import (
    SYSTEM_PROMPT,
    AIError,
    build_ai_input,
    check_answer,
    summarize,
)
from status_report.metrics import calculate
from status_report.project import project_status

START, END = date(2026, 10, 19), date(2026, 10, 25)

GOOD = {
    "summary": "The project is Red. SRG-1 is blocked and has the P1 priority. "
    "One ticket was closed this week.",
    "next_week": ["Remove the blocker on SRG-1."],
}


class FakeClient:
    def __init__(self, answer=GOOD, error=None):
        self.answer = answer
        self.error = error
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(content=[SimpleNamespace(text=text)],
                               usage=SimpleNamespace(input_tokens=900, output_tokens=120))


def week(config=CONFIG):
    tickets = [
        replace(ticket("SRG-1", created=at(5), history=[change(at(21), "To Do", "Blocked")]),
                priority="Highest", title="Secret project Falcon", assignee="Jane Doe"),
        replace(ticket("SRG-2", history=[change(at(21), "To Do", "Done")]),
                title="Closed work", assignee="john@example.com"),
        replace(ticket("SRG-3", created=at(5)), title="Green work", assignee="Jane Doe"),
    ]
    metrics = calculate(tickets, config, START, END)
    status = project_status(tickets, metrics, config)
    return build_ai_input(tickets, metrics, status, config)


# --- What goes to the AI (D03, D28) --------------------------------------------------

def test_input_has_only_the_allowed_facts():
    data = week()
    assert set(data) == {"week", "project_status", "reason", "numbers", "matrix", "tickets"}
    assert data["project_status"] == "Red"
    for row in data["tickets"]:
        assert set(row) <= {"key", "priority", "status", "days_blocked", "title"}


def test_input_never_has_names_emails_or_descriptions():
    # C5 from the Sprint 1 review (D28).
    text = json.dumps(week())
    for private in ("Jane Doe", "john@example.com", "assignee", "description", "comment"):
        assert private not in text


def test_green_tickets_are_only_in_the_counts():
    keys = [row["key"] for row in week()["tickets"]]
    assert keys == ["SRG-1", "SRG-2"]  # Red first, then closed; green SRG-3 is left out


def test_prompt_tells_the_ai_to_use_facts_only_and_keep_the_status():
    assert "Use only the facts in the input" in SYSTEM_PROMPT
    assert "Do not change, question" in SYSTEM_PROMPT
    assert "3 to 5" in SYSTEM_PROMPT and "Next week" in SYSTEM_PROMPT


# --- Checks on the answer -------------------------------------------------------------

def test_good_answer_passes():
    summary = check_answer(json.dumps(GOOD), week())
    assert summary.text.startswith("The project is Red.")
    assert summary.next_week == ("Remove the blocker on SRG-1.",)


def test_unknown_ticket_key_removes_the_summary():
    bad = dict(GOOD, summary=GOOD["summary"] + " SRG-99 is late.")
    with pytest.raises(AIError, match="SRG-99"):
        check_answer(json.dumps(bad), week())


def test_unknown_key_in_next_week_removes_the_summary():
    with pytest.raises(AIError, match="SRG-42"):
        check_answer(json.dumps(dict(GOOD, next_week=["Start SRG-42."])), week())


def test_wrong_number_of_sentences_removes_the_summary():
    with pytest.raises(AIError, match="3 to 5 sentences"):
        check_answer(json.dumps(dict(GOOD, summary="The project is Red.")), week())


def test_summary_that_changes_the_status_is_removed():
    # D02: the rules set the status. An AI text without "Red" is not accepted.
    soft = dict(GOOD, summary="The project is fine. Most work is on track. One item waits.")
    with pytest.raises(AIError, match="D02"):
        check_answer(json.dumps(soft), week())


def test_answer_not_in_json_is_removed():
    with pytest.raises(AIError, match="agreed form"):
        check_answer("Here is your summary: all good.", week())


def test_empty_next_week_is_removed():
    with pytest.raises(AIError, match="Next week"):
        check_answer(json.dumps(dict(GOOD, next_week=[])), week())


# --- The call: model, token limit (D25) ------------------------------------------------

def test_model_and_limits_come_from_config():
    client = FakeClient()
    summary = summarize(week(), CONFIG, client)
    call = client.calls[0]
    assert call["model"] == CONFIG.ai_model
    assert call["max_tokens"] <= CONFIG.max_tokens_per_run
    assert (summary.input_tokens, summary.output_tokens) == (900, 120)


def test_token_limit_stops_the_call():
    client = FakeClient()
    with pytest.raises(AIError, match="max_tokens_per_run"):
        summarize(week(), replace(CONFIG, max_tokens_per_run=100), client)
    assert client.calls == []


# --- The summary cannot negate or change the status (SRG-34, D41) ----------------------

TWO = " SRG-1 is blocked. One ticket was closed this week."


@pytest.mark.parametrize(
    "first",
    [
        "The project is not Red.",
        "The project is no longer Red.",
        "The project isn't Red.",
        "The project is Green, not Red.",
        "The project is Red rather than Amber, but it is out of Red soon.",
        "The project moved from Red to Amber.",
        "The project is Red, but the project is Green overall.",
        "The project status is Amber, not Red.",
    ],
)
def test_summary_that_negates_or_changes_the_status_is_removed(first):
    bad = dict(GOOD, summary=first + TWO)
    with pytest.raises(AIError, match="D02"):
        check_answer(json.dumps(bad), week())


def test_status_must_be_in_the_first_sentence():
    late = dict(GOOD, summary="Work continued this week. SRG-1 is blocked. The project is Red.")
    with pytest.raises(AIError, match="D02"):
        check_answer(json.dumps(late), week())


def test_soft_words_about_the_project_are_removed_when_not_green():
    soft = dict(GOOD, summary="The project is Red. The project is on track overall." + TWO[:18])
    with pytest.raises(AIError, match="softens"):
        check_answer(json.dumps(soft), week())


@pytest.mark.parametrize(
    "text",
    [
        "The project is Red. SRG-1 is Red because it is blocked. One ticket was closed.",
        "The project is Red. The project status stays Red until SRG-1 is free. One was closed.",
        "Project status: Red. SRG-1 has the P1 priority and is blocked. One ticket was closed.",
    ],
)
def test_correct_summaries_still_pass(text):
    assert check_answer(json.dumps(dict(GOOD, summary=text)), week()).text == text


def test_green_week_can_say_on_track():
    from status_report.ai import _check_status

    _check_status("The project is Green. The project is on track. Six tickets closed.", "Green")
