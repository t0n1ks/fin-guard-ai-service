from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import learner

client = TestClient(app)
VALID_KEY = "changeme_shared_secret"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Point the learner at a throwaway file backend per test (no DB, no repo writes)."""
    monkeypatch.setattr(learner, "_USE_DB", False)
    monkeypatch.setattr(learner, "_STATE_FILE", str(tmp_path / "learner_state.json"))
    yield


# ─── Unit: O(1) EWMA correctness ──────────────────────────────────────────────

def test_first_observation_seeds_level():
    state = learner.record_observation(1, daily_spend=20.0, daily_savings=5.0)
    assert state["observations"] == 1
    assert state["ewma_daily_spend"] == 20.0
    assert state["ewma_daily_savings"] == 5.0


def test_subsequent_observation_blends_with_alpha():
    learner.record_observation(1, daily_spend=20.0)
    state = learner.record_observation(1, daily_spend=40.0)
    # alpha=0.3 → 0.3*40 + 0.7*20 = 26.0
    assert state["ewma_daily_spend"] == pytest.approx(26.0)
    assert state["observations"] == 2


def test_negative_inputs_clamped():
    state = learner.record_observation(1, daily_spend=-50.0, daily_savings=-3.0)
    assert state["ewma_daily_spend"] == 0.0
    assert state["ewma_daily_savings"] == 0.0


# ─── Multi-tenant isolation ───────────────────────────────────────────────────

def test_users_are_strictly_isolated():
    learner.record_observation(1, daily_spend=100.0)
    learner.record_observation(2, daily_spend=10.0)
    # Folding more into user 1 must not move user 2 at all.
    learner.record_observation(1, daily_spend=100.0)
    p1 = learner.get_profile(1)
    p2 = learner.get_profile(2)
    assert p1["ewma_daily_spend"] == pytest.approx(100.0)
    assert p2["ewma_daily_spend"] == pytest.approx(10.0)
    assert p2["observations"] == 1


def test_unknown_user_has_no_profile():
    assert learner.get_profile(999) is None


# ─── Prediction ───────────────────────────────────────────────────────────────

def test_predict_projects_from_smoothed_rates():
    state = learner.record_observation(1, daily_spend=15.0, daily_savings=4.0)
    pred = learner.predict(state, days_remaining=10, current_savings_balance=200.0)
    assert pred["projected_spend"] == pytest.approx(150.0)
    assert pred["projected_savings_balance"] == pytest.approx(240.0)


def test_predict_none_state_is_safe():
    pred = learner.predict(None, days_remaining=10, current_savings_balance=200.0)
    assert pred["projected_spend"] == 0.0
    assert pred["projected_savings_balance"] == 200.0


# ─── Endpoint: /v1/learn ──────────────────────────────────────────────────────

def test_learn_endpoint_updates_and_projects():
    r = client.post(
        "/v1/learn",
        headers={"X-Brain-API-Key": VALID_KEY},
        json={
            "user_id": 7,
            "observed_daily_spend": 30.0,
            "observed_daily_savings": 6.0,
            "days_remaining": 5,
            "current_savings_balance": 100.0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == 7
    assert body["observations"] == 1
    assert body["ewma_daily_spend"] == 30.0
    assert body["projected_spend"] == pytest.approx(150.0)
    assert body["projected_savings_balance"] == pytest.approx(130.0)


def test_learn_endpoint_requires_api_key():
    r = client.post("/v1/learn", json={"user_id": 7, "observed_daily_spend": 1.0})
    assert r.status_code == 401
