"""Print the CHANGELOG.md section of one version (SRG-31). Used by the release workflow.

    python scripts/release_notes.py v1.0.0
"""

from __future__ import annotations

import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def notes(tag: str, text: str | None = None) -> str:
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    lines, found = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if found:
                break
            found = line[3:].split()[0] == tag
            continue
        if found:
            lines.append(line)
    if not found:
        raise SystemExit(f"CHANGELOG.md has no section for {tag}.")
    return "\n".join(lines).strip() + "\n"


if __name__ == "__main__":
    print(notes(sys.argv[1]), end="")
