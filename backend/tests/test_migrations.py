from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


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

    command.upgrade(config, "20260827_0001")

    engine = create_engine(database_url)
    user_id = uuid4().hex
    auth_session_id = uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO users (
                    id, email, normalized_email, display_name, password_hash, is_active
                ) VALUES (
                    :id, 'existing@example.com', 'existing@example.com', 'Existing', 'hash', 1
                )"""
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                """INSERT INTO auth_sessions (
                    id, user_id, token_hash, last_seen_at, expires_at
                ) VALUES (
                    :id, :user_id, 'token-hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )"""
            ),
            {"id": auth_session_id, "user_id": user_id},
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {
        "alembic_version",
        "users",
        "auth_sessions",
        "completed_matches",
        "xp_ledger",
        "user_achievements",
        "user_cosmetic_unlocks",
        "user_cosmetic_loadout",
    } == set(inspector.get_table_names())
    assert {"normalized_email"} in [
        set(constraint["column_names"]) for constraint in inspector.get_unique_constraints("users")
    ]
    auth_foreign_keys = inspector.get_foreign_keys("auth_sessions")
    assert auth_foreign_keys[0]["referred_table"] == "users"
    assert auth_foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    match_foreign_keys = inspector.get_foreign_keys("completed_matches")
    assert match_foreign_keys[0]["referred_table"] == "users"
    assert match_foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    assert {"game_session_id"} in [
        set(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("completed_matches")
    ]
    assert {"user_id", "completed_at"} in [
        set(index["column_names"]) for index in inspector.get_indexes("completed_matches")
    ]
    assert {"user_id", "source_key"} in [
        set(index["column_names"])
        for index in inspector.get_indexes("xp_ledger")
        if index["unique"]
    ]
    assert {"user_id", "achievement_code"} in [
        set(index["column_names"])
        for index in inspector.get_indexes("user_achievements")
        if index["unique"]
    ]
    assert {"user_id", "cosmetic_code"} in [
        set(index["column_names"])
        for index in inspector.get_indexes("user_cosmetic_unlocks")
        if index["unique"]
    ]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
        assert connection.scalar(text("SELECT count(*) FROM auth_sessions")) == 1

    command.downgrade(config, "20260827_0003")
    downgraded_tables = set(inspect(engine).get_table_names())
    assert "completed_matches" in downgraded_tables
    assert "xp_ledger" in downgraded_tables
    assert "user_achievements" in downgraded_tables
    assert "user_cosmetic_unlocks" not in downgraded_tables
    assert "user_cosmetic_loadout" not in downgraded_tables
    command.upgrade(config, "head")
    assert {"user_cosmetic_unlocks", "user_cosmetic_loadout"}.issubset(
        inspect(engine).get_table_names()
    )

    command.downgrade(config, "base")

    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
