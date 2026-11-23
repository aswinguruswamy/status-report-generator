"""Make the sample report in examples/ from the demo data (spec SRG-R12; AC34 golden file).

The data is the made-up demo in demo/ (4 teams). Run it after a change to the report layout
or to the demo data:

    python scripts/make_sample.py

A test checks that the file in examples/ is the same as the output of this script.
"""

from __future__ import annotations

from pathlib import Path

from status_report.report import report_name, to_markdown
from status_report.run import load_settings, make_client, read_portfolio

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "examples"


def build() -> dict[str, str]:
    config = load_settings(demo=True)
    portfolio = read_portfolio(make_client(demo=True), config, demo=True, at_start=True)
    return {report_name(portfolio): to_markdown(portfolio)}


def main() -> None:
    FOLDER.mkdir(exist_ok=True)
    for file_name, text in build().items():
        (FOLDER / file_name).write_text(text, encoding="utf-8")
        print(f"Wrote examples/{file_name}")


if __name__ == "__main__":
    main()
