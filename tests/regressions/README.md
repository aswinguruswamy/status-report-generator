# Saved failures (D18)

When a random week fails a survival check, `tests/test_random.py` saves the week here
as `seed-<n>.json`. Commit the file with the fix. Each later test run checks the saved
week again, so the same failure cannot come back.
