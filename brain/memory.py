"""
PAT OS
brain/memory.py

Stores and retrieves PAT's long-term memories using SQLite.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from config import MEMORY_DATABASE


class MemoryManager:
    """Manage PAT's long-term memory database."""

    def __init__(self, database_path: str | Path = MEMORY_DATABASE) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._create_database()

    def _connect(self) -> sqlite3.Connection:
        """Create and return a database connection."""

        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row

        return connection

    def _create_database(self) -> None:
        """Create the memories table if it does not already exist."""

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    memory_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, memory_key: str, memory_value: str) -> tuple[bool, str]:
        """
        Save a new memory or update an existing memory.

        Example:
            key: favorite game
            value: Halo
        """

        cleaned_key = memory_key.strip().lower()
        cleaned_value = memory_value.strip()

        if not cleaned_key or not cleaned_value:
            return False, "I need both a memory name and a value."

        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO memories (
                        memory_key,
                        memory_value,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(memory_key)
                    DO UPDATE SET
                        memory_value = excluded.memory_value,
                        updated_at = excluded.updated_at
                    """,
                    (
                        cleaned_key,
                        cleaned_value,
                        timestamp,
                        timestamp,
                    ),
                )

            return True, f"I'll remember that your {cleaned_key} is {cleaned_value}."

        except sqlite3.Error as error:
            return False, f"I could not save that memory: {error}"

    def get(self, memory_key: str) -> str | None:
        """Retrieve one memory by its key."""

        cleaned_key = memory_key.strip().lower()

        if not cleaned_key:
            return None

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT memory_value
                FROM memories
                WHERE memory_key = ?
                """,
                (cleaned_key,),
            ).fetchone()

        if row is None:
            return None

        return str(row["memory_value"])

    def delete(self, memory_key: str) -> tuple[bool, str]:
        """Delete one stored memory."""

        cleaned_key = memory_key.strip().lower()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM memories
                WHERE memory_key = ?
                """,
                (cleaned_key,),
            )

        if cursor.rowcount == 0:
            return False, f"I do not have a memory named {cleaned_key}."

        return True, f"I forgot your {cleaned_key}."

    def list_all(self) -> list[dict[str, str]]:
        """Return every stored memory."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT memory_key, memory_value, updated_at
                FROM memories
                ORDER BY memory_key
                """
            ).fetchall()

        return [
            {
                "key": str(row["memory_key"]),
                "value": str(row["memory_value"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]


memory_manager = MemoryManager()


def save_memory(memory_key: str, memory_value: str) -> tuple[bool, str]:
    """Convenience function used by other PAT modules."""

    return memory_manager.save(memory_key, memory_value)


def get_memory(memory_key: str) -> str | None:
    """Convenience function used by other PAT modules."""

    return memory_manager.get(memory_key)


def delete_memory(memory_key: str) -> tuple[bool, str]:
    """Convenience function used by other PAT modules."""

    return memory_manager.delete(memory_key)


def list_memories() -> list[dict[str, str]]:
    """Convenience function used by other PAT modules."""

    return memory_manager.list_all()


if __name__ == "__main__":
    print("PAT Memory Test\n")

    success, message = save_memory("favorite game", "Halo")
    print(message)

    favorite_game = get_memory("favorite game")
    print(f"Stored value: {favorite_game}")

    print("\nAll memories:")

    for memory in list_memories():
        print(f"- {memory['key']}: {memory['value']}")