from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_upgrades_and_downgrades_clean_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "migration.sqlite3"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("KIBA_DATABASE_URL", database_url)
    backend_root = Path(__file__).parents[1]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "migrations"))

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert {"alembic_version", "users", "auth_sessions"} == set(inspector.get_table_names())
    assert {"normalized_email"} in [
        set(constraint["column_names"]) for constraint in inspector.get_unique_constraints("users")
    ]
    auth_foreign_keys = inspector.get_foreign_keys("auth_sessions")
    assert auth_foreign_keys[0]["referred_table"] == "users"
    assert auth_foreign_keys[0]["options"]["ondelete"] == "CASCADE"

    command.downgrade(config, "base")

    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
