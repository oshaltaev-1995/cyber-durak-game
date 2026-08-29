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

    command.upgrade(config, "20260827_0002")
    match_id = uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO completed_matches (
                    id, user_id, game_session_id, opponent_type, outcome,
                    started_at, completed_at, duration_seconds, user_seat,
                    initial_attacker, final_human_card_count, final_bot_card_count,
                    human_action_count, human_transfer_count, human_take_count,
                    human_throw_in_count, max_transfer_target,
                    arithmetic_mean_throw_in_count
                ) VALUES (
                    :id, :user_id, 'existing-bot-game', 'BOT', 'WIN',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 'one', 'one',
                    0, 1, 1, 0, 0, 0, 0, 0
                )"""
            ),
            {"id": match_id, "user_id": user_id},
        )

    command.upgrade(config, "20260827_0004")
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO xp_ledger (
                    id, user_id, amount, source_type, source_key, source_match_id
                ) VALUES (
                    :id, :user_id, 100, 'MATCH', 'match:existing', :match_id
                )"""
            ),
            {"id": uuid4().hex, "user_id": user_id, "match_id": match_id},
        )
        connection.execute(
            text(
                """INSERT INTO user_achievements (
                    id, user_id, achievement_code, unlocked_at, unlocked_match_id
                ) VALUES (
                    :id, :user_id, 'FIRST_MATCH', CURRENT_TIMESTAMP, :match_id
                )"""
            ),
            {"id": uuid4().hex, "user_id": user_id, "match_id": match_id},
        )
        connection.execute(
            text(
                """INSERT INTO user_cosmetic_unlocks (
                    id, user_id, cosmetic_code, unlocked_at, source_type, source_key
                ) VALUES (
                    :id, :user_id, 'LEVEL_3_BACK', CURRENT_TIMESTAMP, 'LEVEL', 'level:3'
                )"""
            ),
            {"id": uuid4().hex, "user_id": user_id},
        )
        connection.execute(
            text(
                """INSERT INTO user_cosmetic_loadout (
                    user_id, card_back_code, table_theme_code, profile_frame_code
                ) VALUES (
                    :user_id, 'LEVEL_3_BACK', 'CLASSIC_TABLE', 'NO_FRAME'
                )"""
            ),
            {"user_id": user_id},
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {
        "alembic_version",
        "users",
        "auth_sessions",
        "account_tokens",
        "completed_matches",
        "xp_ledger",
        "user_achievements",
        "user_cosmetic_unlocks",
        "user_cosmetic_loadout",
    } == set(inspector.get_table_names())
    assert "email_verified_at" in {column["name"] for column in inspector.get_columns("users")}
    assert "preferred_locale" in {column["name"] for column in inspector.get_columns("users")}
    assert {"user_id", "token_type"} in [
        set(index["column_names"]) for index in inspector.get_indexes("account_tokens")
    ]
    assert {"normalized_email"} in [
        set(constraint["column_names"]) for constraint in inspector.get_unique_constraints("users")
    ]
    auth_foreign_keys = inspector.get_foreign_keys("auth_sessions")
    assert auth_foreign_keys[0]["referred_table"] == "users"
    assert auth_foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    match_foreign_keys = inspector.get_foreign_keys("completed_matches")
    assert {foreign_key["options"]["ondelete"] for foreign_key in match_foreign_keys} == {
        "CASCADE",
        "SET NULL",
    }
    assert {"game_session_id"} in [
        set(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("completed_matches")
    ]
    assert {"user_id", "completed_at"} in [
        set(index["column_names"]) for index in inspector.get_indexes("completed_matches")
    ]
    assert {"user_id", "pvp_match_id"} in [
        set(index["column_names"])
        for index in inspector.get_indexes("completed_matches")
        if index["unique"]
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
        assert connection.scalar(text("SELECT preferred_locale FROM users")) == "ru"
        assert connection.scalar(text("SELECT count(*) FROM auth_sessions")) == 1
        assert connection.scalar(text("SELECT count(*) FROM completed_matches")) == 1
        assert connection.scalar(text("SELECT opponent_type FROM completed_matches")) == "BOT"
        assert connection.scalar(text("SELECT count(*) FROM xp_ledger")) == 1
        assert connection.scalar(text("SELECT count(*) FROM user_achievements")) == 1
        assert connection.scalar(text("SELECT count(*) FROM user_cosmetic_unlocks")) == 1
        assert connection.scalar(text("SELECT count(*) FROM user_cosmetic_loadout")) == 1

    command.downgrade(config, "20260827_0003")
    downgraded_tables = set(inspect(engine).get_table_names())
    assert "completed_matches" in downgraded_tables
    assert "xp_ledger" in downgraded_tables
    assert "user_achievements" in downgraded_tables
    assert "user_cosmetic_unlocks" not in downgraded_tables
    assert "user_cosmetic_loadout" not in downgraded_tables
    assert "account_tokens" not in downgraded_tables
    command.upgrade(config, "head")
    assert {"user_cosmetic_unlocks", "user_cosmetic_loadout"}.issubset(
        inspect(engine).get_table_names()
    )

    command.downgrade(config, "base")

    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
