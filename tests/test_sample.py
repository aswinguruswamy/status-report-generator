"""The sample report in examples/ is up to date (SRG-29)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("make_sample", ROOT / "scripts" / "make_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_files_match_the_script():
    expected = load_script().build()
    assert sorted(expected) == ["DEMO-2026-W43.html", "DEMO-2026-W43.md"]
    for name, text in expected.items():
        on_disk = (ROOT / "examples" / name).read_text(encoding="utf-8")
        assert on_disk == text, f"examples/{name} is old. Run: python scripts/make_sample.py"


def test_sample_uses_made_up_data_only():
    for name in ("DEMO-2026-W43.md", "DEMO-2026-W43.html"):
        text = (ROOT / "examples" / name).read_text(encoding="utf-8")
        assert "SRG-" not in text  # No real ticket
        assert not re.search(r"[\w.]+@[\w-]+\.\w+", text)  # No email address
        assert "Sample text" in text and "Written by AI" not in text
