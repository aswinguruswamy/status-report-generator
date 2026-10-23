"""AI evaluation set (SRG-24, D12).

Unit tests check the code. This set checks the quality of the AI summary.
Each sample is one week of AI input, plus the facts the summary must contain and
the facts it must not contain. Run it before an AI story is done, and after each
change to the prompt or the model:

    python -m status_report.evaluation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from status_report.ai import AIError, Summary, estimate_tokens, make_client, summarize
from status_report.config import ConfigError, load_config

SAMPLES = Path(__file__).resolve().parent.parent / "eval" / "samples"


@dataclass(frozen=True)
class Result:
    name: str
    passed: bool
    problems: tuple[str, ...]
    tokens: int = 0
    text: str = ""  # The summary and Next week items, shown for a failed sample (SRG-38)


def load_samples(folder: Path = SAMPLES) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE) is not None


def evaluate(sample: dict, summary: Summary) -> Result:
    """Compare one summary with the expected facts of its sample."""
    text = summary.text + "\n" + "\n".join(summary.next_week)
    problems = []
    for phrase in sample.get("must_contain", []):
        if not _has(text, phrase):
            problems.append(f"missing: {phrase}")
    for options in sample.get("must_contain_one_of", []):
        if not any(_has(text, phrase) for phrase in options):
            problems.append(f"missing one of: {' / '.join(options)}")
    for phrase in sample.get("must_not_contain", []):
        if _has(text, phrase):
            problems.append(f"must not contain: {phrase}")
    tokens = summary.input_tokens + summary.output_tokens
    return Result(sample["name"], not problems, tuple(problems), tokens, text)


def run(samples: list[dict], config, client) -> list[Result]:
    results = []
    for sample in samples:
        try:
            summary = summarize(sample["input"], config, client)
        except AIError as error:  # The guardrail checks in ai.py count as a failure
            results.append(Result(sample["name"], False, (str(error),)))
            continue
        results.append(evaluate(sample, summary))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AI evaluation set (real Claude API).")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--yes", action="store_true", help="Do not ask before the API calls.")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ERROR: {error}")
        return 1

    samples = load_samples()
    estimate = sum(estimate_tokens(s["input"]) for s in samples)
    print(f"{len(samples)} samples, model {config.ai_model}, at most about {estimate} tokens in total.")
    if not args.yes and input("Run the calls now? [y/N] ").strip().lower() != "y":
        print("Stopped. No API call was made.")
        return 1
    try:
        client = make_client()
    except AIError as error:
        print(f"ERROR: {error}")
        return 1

    results = run(samples, config, client)
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.name:<16} {r.tokens:>6} tokens  {'; '.join(r.problems)}")
        if not r.passed and r.text:
            print("      " + r.text.replace("\n", "\n      "))  # Show what the AI wrote
    passed = sum(r.passed for r in results)
    print(f"Result: {passed} of {len(results)} passed.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
