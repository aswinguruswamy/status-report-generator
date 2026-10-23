"""Tests for the AI evaluation set (SRG-24, D12). No real API call."""

from __future__ import annotations

import json

from test_ai import FakeClient
from test_metrics import CONFIG

from status_report.ai import KEY_PATTERN, Summary, estimate_tokens
from status_report.evaluation import evaluate, load_samples, run

SAMPLES = load_samples()

GOOD_ANSWERS = {
    "1-red-week": (("The project is Red. WEB-12 has the P1 priority and is blocked for 4 days. "
                   "The team closed 3 tickets and opened 2."), ["Remove the blocker on WEB-12."]),
    "2-amber-week": (("The project is Amber. API-21 and API-22 are due soon and not started. "
                     "The team closed 4 tickets and opened 4."), ["Start API-21 and API-22."]),
    "3-green-week": (("The project is Green. The team closed 6 tickets this week. "
                     "No ticket is blocked or overdue."), ["Continue the open work."]),
    "4-empty-week": (("The project is Green. There are no open tickets this week. "
                     "No ticket was opened or closed."), ["Plan the work for the next week."]),
    "5-hidden-titles": (("The project is Red. FIN-3 has the P1 priority and is overdue. "
                        "FIN-8 is blocked for 2 days."), ["Finish FIN-3.", "Remove the blocker on FIN-8."]),
}


def test_set_has_the_five_required_weeks():
    names = [s["name"] for s in SAMPLES]
    assert names == ["1-red-week", "2-amber-week", "3-green-week", "4-empty-week", "5-hidden-titles"]
    for s in SAMPLES:
        assert s["must_contain"] and s["must_not_contain"], s["name"]


def test_samples_follow_the_ai_input_rules():
    for s in SAMPLES:
        data = s["input"]
        assert set(data) == {"week", "project_status", "reason", "numbers", "matrix", "tickets"}
        assert data["reason"].startswith(data["project_status"] + ":")
        keys = {row["key"] for row in data["tickets"]}
        assert set(KEY_PATTERN.findall(data["reason"])) <= keys, s["name"]
        assert estimate_tokens(data) < CONFIG.max_tokens_per_run
    hidden = next(s for s in SAMPLES if s["name"] == "5-hidden-titles")
    assert all("title" not in row for row in hidden["input"]["tickets"])


def test_good_answers_pass_each_sample():
    for s in SAMPLES:
        text, items = GOOD_ANSWERS[s["name"]]
        result = evaluate(s, Summary(text=text, next_week=tuple(items)))
        assert result.passed, (s["name"], result.problems)


def test_bad_answers_fail():
    red = SAMPLES[0]
    soft = Summary("The project is Green and on track. All is fine. Nothing to do.", ("Relax.",))
    result = evaluate(red, soft)
    assert not result.passed
    assert "missing: Red" in result.problems and "must not contain: on track" in result.problems


def test_runner_counts_guardrail_failures_as_fail():
    # An answer with an unknown key fails in ai.check_answer before the sample checks.
    bad = {"summary": "The project is Red. WEB-99 is late. Act now.", "next_week": ["Fix WEB-99."]}
    results = run(SAMPLES[:1], CONFIG, FakeClient(bad))
    assert not results[0].passed and "WEB-99" in results[0].problems[0]


def test_runner_passes_with_good_answers():
    results = []
    for s in SAMPLES:
        text, items = GOOD_ANSWERS[s["name"]]
        results += run([s], CONFIG, FakeClient(json.loads(json.dumps({"summary": text, "next_week": items}))))
    assert all(r.passed for r in results), [r for r in results if not r.passed]
