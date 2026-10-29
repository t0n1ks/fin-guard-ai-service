import os

# Set test credentials before any app module is imported.
# These values are used only during testing and are never committed.
os.environ.setdefault("BRAIN_API_KEY", "changeme_shared_secret")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Every test gets its own per-user state files (never the real ones)."""
    from app.services import content_tracker, seen_store

    monkeypatch.setattr(seen_store, "STATE_FILE", str(tmp_path / "companion_seen.json"))
    monkeypatch.setattr(seen_store, "_USE_DB", False)
    monkeypatch.setattr(content_tracker, "STATE_FILE", str(tmp_path / "daily_state.json"))
    monkeypatch.setattr(content_tracker, "_USE_DB", False)
