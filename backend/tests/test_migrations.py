"""Tests verifying Alembic database migration upgrade, downgrade, and re-upgrade."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command


@pytest.mark.asyncio
async def test_migration_lifecycle(db_session: AsyncSession) -> None:
    """Verify programmatic migration downgrade to base and re-upgrade to head."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # 1. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    # Verify tables dropped
    res = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
    )
    remaining_tables = [row[0] for row in res.fetchall()]
    assert len(remaining_tables) == 0

    # 2. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Verify all 7 domain tables restored
    res = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
    )
    recreated_tables = {row[0] for row in res.fetchall()}
    expected_tables = {
        "organizations",
        "users",
        "organization_memberships",
        "teams",
        "team_memberships",
        "services",
        "service_dependencies",
    }
    assert expected_tables.issubset(recreated_tables)
