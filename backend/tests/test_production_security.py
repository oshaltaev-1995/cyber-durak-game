from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from kiba_api.config import AppEnvironment, EmailMode, Settings
from kiba_api.main import create_app
from kiba_api.persistence import Base, Database

ORIGIN = "https://kiba.example.test"


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": AppEnvironment.PRODUCTION,
        "database_url": "postgresql+psycopg://kiba:strong-password@database:5432/kiba",
        "public_base_url": ORIGIN,
        "trusted_hosts": ("kiba.example.test",),
        "csrf_trusted_origins": (ORIGIN,),
        "auth_cookie_secure": True,
        "email_mode": EmailMode.SMTP,
        "smtp_host": "smtp.example.test",
        "smtp_username": "kiba",
        "smtp_password": "smtp-secret",
        "smtp_from": "no-reply@example.test",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("auth_cookie_secure", False),
        ("public_base_url", "http://localhost:14200"),
        ("public_base_url", ""),
        ("trusted_hosts", ("*",)),
        ("trusted_hosts", ()),
        ("csrf_trusted_origins", ("*",)),
        ("email_mode", EmailMode.DEVELOPMENT),
        ("smtp_password", None),
    ],
)
def test_production_configuration_rejects_unsafe_values(key: str, value) -> None:
    with pytest.raises(ValueError, match="unsafe production configuration"):
        production_settings(**{key: value})


def test_production_configuration_rejects_default_database() -> None:
    with pytest.raises(ValueError, match="development default"):
        production_settings(database_url="postgresql+psycopg://kiba:kiba@database:5432/kiba")


def test_production_headers_request_id_host_and_origin_policy() -> None:
    database = Database("sqlite://")
    Base.metadata.create_all(database.engine)
    # Settings must validate a production URL while the injected test database remains isolated.
    settings = production_settings()
    client = TestClient(create_app(database=database, settings=settings))

    response = client.get("/health", headers={"host": "kiba.example.test"})
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"]
    assert response.headers["x-request-id"]
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 400
    missing_origin = client.post(
        "/api/auth/login",
        headers={"host": "kiba.example.test"},
        json={"email": "none@example.com", "password": "incorrect"},
    )
    assert missing_origin.status_code == 403
    database.dispose()


def test_ready_reports_database_health() -> None:
    database = Database("sqlite://")
    Base.metadata.create_all(database.engine)
    client = TestClient(
        create_app(
            database=database,
            settings=Settings(app_env="test", database_url="sqlite://"),
        )
    )
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


class FailingEngine:
    @contextmanager
    def connect(self):
        raise OSError("database unavailable")
        yield


class FailingDatabase:
    engine = FailingEngine()

    @contextmanager
    def session(self):
        raise OSError("not used")
        yield

    def dispose(self) -> None:
        pass


def test_ready_is_503_but_health_remains_live_when_database_is_unavailable() -> None:
    client = TestClient(
        create_app(
            database=FailingDatabase(),  # type: ignore[arg-type]
            settings=Settings(app_env="test", database_url="sqlite://"),
        )
    )
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
