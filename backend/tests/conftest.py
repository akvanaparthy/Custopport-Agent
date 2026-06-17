"""Shared fixtures. `client` builds the app against a throwaway temp DB (via the
DB_PATH env var), so the lifespan inits + seeds an isolated database per test and
the real dependency wiring is exercised end to end."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    from app.config import get_settings

    get_settings.cache_clear()  # re-read env with the temp DB_PATH
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:  # runs lifespan -> init schema + seed
        yield c
    get_settings.cache_clear()
