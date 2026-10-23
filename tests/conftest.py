"""Test settings for all tests."""

import pytest

from status_report import ai, cli


@pytest.fixture(autouse=True)
def no_real_ai_calls(monkeypatch):
    """No test may call the real Claude API or use the real key in .env."""

    def blocked():
        raise ai.AIError("Real AI calls are blocked in tests.")

    monkeypatch.setattr(ai, "make_client", blocked)
    monkeypatch.setattr(cli, "make_client", blocked)
