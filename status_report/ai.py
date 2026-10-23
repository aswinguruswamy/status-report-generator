"""Executive summary from facts only (SRG-23, SRG-25, SRG-26).

Guardrails (D02, D03, D25, D28, AI Guardrails page):
- The AI gets only: counts, the matrix, the project status and reason, and ticket keys,
  priorities, ticket statuses, and titles. Titles only when hide_titles_from_ai is false.
- The AI never gets descriptions, comments, assignee names, or email addresses.
- The rules set the status. The AI only explains it.
- The tool checks the answer. A wrong answer is removed, and the report shows a warning.
- If the AI fails, the report is made without the summary (SRG-25).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from status_report.config import Config
from status_report.metrics import WeekMetrics
from status_report.models import Ticket
from status_report.project import ProjectStatus

MAX_OUTPUT_TOKENS = 600
TIMEOUT_SECONDS = 60
CHARS_PER_TOKEN = 3  # A safe estimate: real text has about 4 characters for each token
KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

SYSTEM_PROMPT = """You write the executive summary of a weekly project status report.

Rules:
1. Use only the facts in the input. Do not add facts, causes, people, or dates.
2. The project status and its reason are set by fixed rules. Do not change, question,
   or soften the status. Write the status word exactly as in the input.
3. Name only ticket keys that are in the input.
4. Do not name or blame a person.
5. Write 3 to 5 short sentences in plain, neutral English.
6. Then give 1 to 5 short "Next week" items. Each item comes from the facts, for
   example a blocked, overdue, or at-risk ticket.

Answer with JSON only, in this form:
{"summary": "<3 to 5 sentences>", "next_week": ["<item>", "..."]}"""


class AIError(Exception):
    """The summary is not available. The report is made without it."""


@dataclass(frozen=True)
class Summary:
    text: str
    next_week: tuple[str, ...]
    input_tokens: int = 0
    output_tokens: int = 0


# --- What goes to the AI ------------------------------------------------------------

def build_ai_input(
    tickets: list[Ticket], metrics: WeekMetrics, status: ProjectStatus, config: Config
) -> dict:
    """The only data that goes to the AI. See the module text for the rules."""
    statuses = status.ticket_status
    closed = set(metrics.closed)
    # Green tickets are only in the counts. This keeps the input small for big projects.
    listed = [t for t in tickets if statuses.get(t.key, "Green") != "Green" or t.key in closed]
    order = {"Black": 0, "Red": 1, "Amber": 2, "Green": 3}
    listed.sort(key=lambda t: (order.get(statuses.get(t.key, ""), 4), t.key))

    rows = []
    for t in listed:
        row = {
            "key": t.key,
            "priority": config.priority_level(t.priority),
            "status": statuses.get(t.key, "Done this week"),
        }
        if t.key in metrics.days_blocked and metrics.days_blocked[t.key] is not None:
            row["days_blocked"] = metrics.days_blocked[t.key]
        if not config.hide_titles_from_ai:
            row["title"] = t.title
        rows.append(row)

    return {
        "week": f"{metrics.start} to {metrics.end}",
        "project_status": status.status,
        "reason": status.reason,
        "numbers": metrics.counts(),
        "matrix": status.counts(),
        "tickets": rows,
    }


def estimate_tokens(ai_input: dict) -> int:
    text = SYSTEM_PROMPT + json.dumps(ai_input, ensure_ascii=False)
    return len(text) // CHARS_PER_TOKEN + MAX_OUTPUT_TOKENS


# --- Check the answer ------------------------------------------------------------------

def _sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def check_answer(raw: str, ai_input: dict) -> Summary:
    """Parse and check the AI answer. Raise AIError if it breaks a rule."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise AIError("The AI answer is not in the agreed form.")
    try:
        data = json.loads(match.group(0))
        text = str(data["summary"]).strip()
        next_week = tuple(str(item).strip() for item in data["next_week"] if str(item).strip())
    except (ValueError, KeyError, TypeError):
        raise AIError("The AI answer is not in the agreed form.") from None

    if not 3 <= _sentences(text) <= 5:
        raise AIError("The AI summary does not have 3 to 5 sentences.")
    if not 1 <= len(next_week) <= 5:
        raise AIError("The AI summary does not have 1 to 5 'Next week' items.")

    allowed = {row["key"] for row in ai_input["tickets"]} | set(KEY_PATTERN.findall(ai_input["reason"]))
    unknown = set(KEY_PATTERN.findall(text + " " + " ".join(next_week))) - allowed
    if unknown:
        raise AIError(f"The AI summary names tickets that are not in the input: {', '.join(sorted(unknown))}.")

    if not re.search(rf"\b{ai_input['project_status']}\b", text, re.IGNORECASE):
        raise AIError("The AI summary does not state the project status from the rules (D02).")
    return Summary(text=text, next_week=next_week)


# --- Call the AI -------------------------------------------------------------------------

def make_client():
    """The Claude API client, with the key from .env."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise AIError("ANTHROPIC_API_KEY is missing in .env.")
    import anthropic

    return anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=2)


def summarize(ai_input: dict, config: Config, client) -> Summary:
    """Ask the AI for the summary and check it. Raise AIError on each problem."""
    estimate = estimate_tokens(ai_input)
    if estimate > config.max_tokens_per_run:
        raise AIError(
            f"The AI input needs about {estimate} tokens. The limit in config.yaml is "
            f"{config.max_tokens_per_run} (max_tokens_per_run)."
        )
    import anthropic

    try:
        response = client.messages.create(
            model=config.ai_model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(ai_input, ensure_ascii=False)}],
        )
    except (anthropic.AnthropicError, OSError, TimeoutError) as error:
        # API errors, timeouts, and network errors all mean: no summary this week.
        raise AIError(f"The Claude API call failed ({type(error).__name__}).") from None

    raw = "".join(getattr(block, "text", "") for block in response.content)
    summary = check_answer(raw, ai_input)
    usage = getattr(response, "usage", None)
    return Summary(
        text=summary.text,
        next_week=summary.next_week,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )
