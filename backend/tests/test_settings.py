"""Tier-1: env defaults overlaid by SQLite overrides; canonical keys only;
sampling params rejected at the schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts import Effort, IdentityMode
from app.db.database import connect
from app.observability.db import init_observability
from app.settings.schema import SettingsUpdate
from app.settings.store import get_effective_config, update_settings


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_observability(c)
    yield c
    c.close()


def test_defaults_when_no_override(conn):
    cfg = get_effective_config(conn)
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.effort is Effort.MEDIUM
    assert cfg.max_tokens == 4096
    assert cfg.identity_mode is IdentityMode.AUTHENTICATED


def test_override_takes_effect(conn):
    view = update_settings(conn, SettingsUpdate(model="claude-haiku-4-5", effort=Effort.LOW))
    assert view.model == "claude-haiku-4-5"
    assert view.source_map["model"] == "override"
    assert view.source_map["persona"] == "env"  # untouched
    # a fresh read reflects it (simulates the next agent message)
    assert get_effective_config(conn).model == "claude-haiku-4-5"
    assert get_effective_config(conn).effort is Effort.LOW


def test_partial_update_keeps_other_overrides(conn):
    update_settings(conn, SettingsUpdate(model="claude-opus-4-8"))
    update_settings(conn, SettingsUpdate(max_tokens=8000))
    cfg = get_effective_config(conn)
    assert cfg.model == "claude-opus-4-8"  # still set
    assert cfg.max_tokens == 8000


def test_sampling_params_rejected():
    with pytest.raises(ValidationError):
        SettingsUpdate(temperature=0.5)  # extra='forbid'


def test_max_tokens_ceiling_enforced():
    with pytest.raises(ValidationError):
        SettingsUpdate(max_tokens=64000)  # > MAX_TOKENS_CEILING (16000)


def test_unsupported_model_rejected():
    with pytest.raises(ValidationError):
        SettingsUpdate(model="gpt-4")
