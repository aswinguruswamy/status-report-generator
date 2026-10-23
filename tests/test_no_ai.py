"""The report never stops because of the AI (SRG-25).

Charter risk: "The Claude API is not available."
"""

from __future__ import annotations

import re
from datetime import date

import anthropic
import httpx2 as httpx
from test_ai import FakeClient as FakeAI
from test_cli import REPO_CONFIG, FakeClient, ticket

from status_report.cli import EXIT_OK, main

REPORT = "status-report-SRG-2026-10-19.md"
GOOD = {
    "summary": "The project is Amber. SRG-1 is due soon and not started. No ticket was closed.",
    "next_week": ["Start SRG-1."],
}


def make(tmp_path, *args, ai=None):
    argv = ["--config", REPO_CONFIG, "--output", str(tmp_path), "--week", "2026-10-19",
            "--format", "md", *args]
    code = main(argv, client=FakeClient([ticket()]), today=date(2026, 10, 22), ai_client=ai)
    return code, (tmp_path / REPORT).read_text()


def without_ai_parts(text: str) -> str:
    text = re.sub(r"## Executive summary.*?(?=## Weekly numbers)", "", text, flags=re.DOTALL)
    return re.sub(r"\n## Warnings.*?(?=\n## Tickets)", "", text, flags=re.DOTALL)


def test_no_ai_option_makes_no_call_and_no_summary(tmp_path, capsys):
    ai = FakeAI(GOOD)
    code, text = make(tmp_path, "--no-ai", ai=ai)
    assert code == EXIT_OK
    assert ai.calls == []
    assert "## Executive summary" not in text
    assert "AI summary: off" in capsys.readouterr().out


def test_api_connection_error_still_makes_the_report(tmp_path):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    ai = FakeAI(error=anthropic.APIConnectionError(request=request))
    code, text = make(tmp_path, ai=ai)
    assert code == EXIT_OK
    assert "## Executive summary" not in text
    assert "No AI summary in this report. The Claude API call failed (APIConnectionError)." in text


def test_api_timeout_still_makes_the_report(tmp_path):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    code, text = make(tmp_path, ai=FakeAI(error=anthropic.APITimeoutError(request=request)))
    assert code == EXIT_OK
    assert "The Claude API call failed (APITimeoutError)." in text


def test_missing_api_key_still_makes_the_report(tmp_path):
    code, text = make(tmp_path)  # No AI client: the test guard acts as a missing key
    assert code == EXIT_OK
    assert "No AI summary in this report." in text


def test_status_matrix_and_numbers_are_the_same_with_or_without_ai(tmp_path):
    _, with_ai = make(tmp_path / "a", ai=FakeAI(GOOD))
    _, without = make(tmp_path / "b", "--no-ai")
    assert "## Executive summary" in with_ai
    assert without_ai_parts(with_ai) == without_ai_parts(without)
