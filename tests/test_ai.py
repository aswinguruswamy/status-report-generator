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
    """A fake Claude API. Like structured outputs, it answers with JSON text (SRG-40)."""

    def __init__(self, answer=GOOD, error=None, stop_reason="end_turn"):
        self.answer = answer
        self.error = error
        self.stop_reason = stop_reason
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=900, output_tokens=120),
                               stop_reason=self.stop_reason)


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
    with pytest.raises(AIError, match="on track"):
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


# --- Soft words anywhere in a week that is not Green (SRG-38, D44) ----------------------

def test_soft_words_in_any_sentence_are_removed():
    # The evaluation run found this: "on track" in a sentence without "project".
    soft = dict(GOOD, summary="The project is Red. SRG-1 is blocked. Other work is on track.")
    with pytest.raises(AIError, match="D44"):
        check_answer(json.dumps(soft), week())


def test_soft_words_in_next_week_are_removed():
    with pytest.raises(AIError, match="D44"):
        check_answer(json.dumps(dict(GOOD, next_week=["Keep the release on track."])), week())


@pytest.mark.parametrize("word", ["healthy", "no risks", "no concerns", "no issues", "all good"])
def test_each_soft_word_is_removed(word):
    soft = dict(GOOD, summary=f"The project is Red. SRG-1 is blocked. The rest has {word}.")
    with pytest.raises(AIError, match="D44"):
        check_answer(json.dumps(soft), week())


def test_prompt_forbids_soft_words_when_not_green():
    assert '"on track"' in SYSTEM_PROMPT and "not Green" in SYSTEM_PROMPT


# --- Structured outputs and clear error reasons (SRG-40, D49) ----------------------------

def test_the_call_asks_for_structured_output_and_no_forced_tool():
    # Claude Sonnet 5.5 refuses a forced tool call with a 400 error (real run 2).
    client = FakeClient()
    summarize(week(), CONFIG, client)
    call = client.calls[0]
    schema = call["output_config"]["format"]["schema"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert set(schema["required"]) == {"summary", "next_week"}
    assert schema["additionalProperties"] is False
    assert "tool_choice" not in call and "tools" not in call


def test_schema_uses_only_supported_keywords():
    # Structured outputs reject maxItems, minLength, maxLength, minimum, and maximum.
    from status_report.ai import SUMMARY_SCHEMA

    text = json.dumps(SUMMARY_SCHEMA)
    for keyword in ("maxItems", "minLength", "maxLength", "minimum", "maximum", "$ref"):
        assert keyword not in text


def test_answer_with_quotes_braces_and_line_breaks_passes():
    answer = {"summary": 'The project is Red. SRG-1 "Secret {project}" is blocked.\nOne closed.',
              "next_week": ['Free SRG-1 ("Secret {project}").']}
    summary = summarize(week(), CONFIG, FakeClient(answer))
    assert '"Secret {project}"' in summary.text


def test_broken_json_states_the_reason():
    broken = '{"summary": "The project is Red. SRG-1 "Secret" is blocked. One closed.", "next_week": []}'
    with pytest.raises(AIError, match=r"agreed form: JSON error .* at character \d+"):
        summarize(week(), CONFIG, FakeClient(broken))


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ("Here is the summary.", "has no JSON object"),
        ({"summary": "The project is Red."}, "the field next_week is missing"),
        ({"summary": 3, "next_week": []}, "must be text"),
    ],
)
def test_each_form_error_states_its_reason(answer, reason):
    with pytest.raises(AIError, match=reason):
        summarize(week(), CONFIG, FakeClient(answer))


@pytest.mark.parametrize(("stop", "reason"), [("max_tokens", "output limit"), ("refusal", "refused")])
def test_stop_reasons_are_stated(stop, reason):
    with pytest.raises(AIError, match=reason):
        summarize(week(), CONFIG, FakeClient(GOOD, stop_reason=stop))


def test_api_error_states_the_status_and_the_message():
    import anthropic
    import httpx2 as httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.BadRequestError(
        "tool_choice is not supported for this model", response=httpx.Response(400, request=request),
        body=None,
    )
    with pytest.raises(AIError, match=r"BadRequestError, 400: tool_choice is not supported"):
        summarize(week(), CONFIG, FakeClient(error=error))
