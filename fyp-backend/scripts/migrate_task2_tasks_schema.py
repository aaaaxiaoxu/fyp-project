from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import engine, init_db


TASKS_PROJECT_FK_NAME = "fk_tasks_project_id_set_null"
TASKS_SIMULATION_FK_NAME = "fk_tasks_simulation_id_set_null"


async def _fetch_fk_metadata(conn, schema_name: str, column_name: str) -> dict | None:
    result = await conn.execute(
        text(
            """
            SELECT
                kcu.CONSTRAINT_NAME,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME,
                rc.DELETE_RULE
            FROM information_schema.KEY_COLUMN_USAGE AS kcu
            JOIN information_schema.REFERENTIAL_CONSTRAINTS AS rc
              ON rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
             AND rc.TABLE_NAME = kcu.TABLE_NAME
             AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE kcu.CONSTRAINT_SCHEMA = :schema_name
              AND kcu.TABLE_NAME = 'tasks'
              AND kcu.COLUMN_NAME = :column_name
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            """
        ),
        {"schema_name": schema_name, "column_name": column_name},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _ensure_tasks_message_column(conn, schema_name: str) -> list[str]:
    result = await conn.execute(
        text(
            """
            SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLUMN_DEFAULT, IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema_name
              AND TABLE_NAME = 'tasks'
              AND COLUMN_NAME = 'message'
            """
        ),
        {"schema_name": schema_name},
    )
    row = result.mappings().first()
    if row is None:
        raise RuntimeError("tasks.message column not found")

    changes: list[str] = []
    needs_alter = not (
        row["DATA_TYPE"] == "varchar"
        and row["CHARACTER_MAXIMUM_LENGTH"] == 1024
        and (row["COLUMN_DEFAULT"] or "") == ""
        and row["IS_NULLABLE"] == "NO"
    )
    if not needs_alter:
        return changes

    max_length_result = await conn.execute(text("SELECT MAX(CHAR_LENGTH(message)) AS max_len FROM tasks"))
    max_len = max_length_result.scalar_one()
    if max_len is not None and max_len > 1024:
        raise RuntimeError(f"tasks.message contains values longer than 1024 characters (max={max_len})")

    await conn.execute(text("ALTER TABLE tasks MODIFY COLUMN message VARCHAR(1024) NOT NULL DEFAULT ''"))
    changes.append("updated tasks.message to VARCHAR(1024) NOT NULL DEFAULT ''")
    return changes


async def _ensure_nullable_task_parent_columns(conn) -> list[str]:
    await conn.execute(text("ALTER TABLE tasks MODIFY COLUMN project_id VARCHAR(64) NULL"))
    await conn.execute(text("ALTER TABLE tasks MODIFY COLUMN simulation_id VARCHAR(64) NULL"))
    return [
        "ensured tasks.project_id is nullable",
        "ensured tasks.simulation_id is nullable",
    ]


async def _ensure_fk_with_set_null(
    conn,
    schema_name: str,
    column_name: str,
    target_table: str,
    constraint_name: str,
) -> list[str]:
    fk = await _fetch_fk_metadata(conn, schema_name, column_name)
    changes: list[str] = []

    if fk and fk["DELETE_RULE"] == "SET NULL":
        return changes

    if fk:
        await conn.execute(text(f"ALTER TABLE tasks DROP FOREIGN KEY {fk['CONSTRAINT_NAME']}"))
        changes.append(f"dropped old FK {fk['CONSTRAINT_NAME']} on tasks.{column_name}")

    await conn.execute(
        text(
            f"""
            ALTER TABLE tasks
            ADD CONSTRAINT {constraint_name}
            FOREIGN KEY ({column_name}) REFERENCES {target_table}(id)
            ON DELETE SET NULL
            """
        )
    )
    changes.append(f"added FK {constraint_name} with ON DELETE SET NULL on tasks.{column_name}")
    return changes


async def main() -> None:
    await init_db()

    if engine.url.get_backend_name() != "mysql":
        raise RuntimeError("This migration script only supports MySQL backends.")

    schema_name = engine.url.database
    if not schema_name:
        raise RuntimeError("Unable to determine current database name.")

    changes: list[str] = []
    async with engine.begin() as conn:
        changes.extend(await _ensure_tasks_message_column(conn, schema_name))
        changes.extend(await _ensure_nullable_task_parent_columns(conn))
        changes.extend(
            await _ensure_fk_with_set_null(
                conn,
                schema_name,
                column_name="project_id",
                target_table="projects",
                constraint_name=TASKS_PROJECT_FK_NAME,
            )
        )
        changes.extend(
            await _ensure_fk_with_set_null(
                conn,
                schema_name,
                column_name="simulation_id",
                target_table="simulations",
                constraint_name=TASKS_SIMULATION_FK_NAME,
            )
        )

    if changes:
        print("migration_applied")
        for item in changes:
            print(f"- {item}")
    else:
        print("migration_already_up_to_date")


if __name__ == "__main__":
    asyncio.run(main())
