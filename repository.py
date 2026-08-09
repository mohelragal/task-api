import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row


SEED_TASKS = [
    ("Learn HTTP basics", True),
    ("Build a CRUD API", False),
    ("Test with Swagger UI", False),
]


class TaskRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.sqlite = database_url.startswith("sqlite:///")

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.sqlite:
            connection = sqlite3.connect(self.database_url.removeprefix("sqlite:///"))
            connection.row_factory = sqlite3.Row
        else:
            connection = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def sql(self, query: str) -> str:
        return query.replace("%s", "?") if self.sqlite else query

    def value(self, row: Any) -> Any:
        return next(iter(row.values())) if isinstance(row, dict) else row[0]

    def execute_many(self, connection: Any, query: str, parameters: list[tuple]) -> None:
        if self.sqlite:
            connection.executemany(self.sql(query), parameters)
        else:
            with connection.cursor() as cursor:
                cursor.executemany(query, parameters)

    def initialize(self) -> None:
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.sqlite else "SERIAL PRIMARY KEY"
        with self.connection() as connection:
            connection.execute(
                f"CREATE TABLE IF NOT EXISTS tasks (id {id_column}, title TEXT NOT NULL, done BOOLEAN NOT NULL DEFAULT FALSE)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")
            count = self.value(connection.execute("SELECT COUNT(*) FROM tasks").fetchone())
            if count == 0:
                self.execute_many(
                    connection,
                    "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                    SEED_TASKS,
                )

    def health(self) -> bool:
        with self.connection() as connection:
            return self.value(connection.execute("SELECT 1").fetchone()) == 1

    def list_tasks(self, done: bool | None = None, search: str | None = None) -> list[dict]:
        clauses = []
        parameters = []
        if done is not None:
            clauses.append("done = %s")
            parameters.append(done)
        if search:
            clauses.append(f"title {'LIKE' if self.sqlite else 'ILIKE'} %s")
            parameters.append(f"%{search}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connection() as connection:
            rows = connection.execute(
                self.sql(f"SELECT id, title, done FROM tasks{where} ORDER BY id"),
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, task_id: int) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                self.sql("SELECT id, title, done FROM tasks WHERE id = %s"),
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def create(self, title: str) -> dict:
        with self.connection() as connection:
            if self.sqlite:
                cursor = connection.execute(
                    "INSERT INTO tasks (title, done) VALUES (?, ?) RETURNING id, title, done",
                    (title, False),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING id, title, done",
                    (title, False),
                )
            return dict(cursor.fetchone())

    def update(self, task_id: int, title: str, done: bool) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                self.sql(
                    "UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING id, title, done"
                ),
                (title, done, task_id),
            ).fetchone()
        return dict(row) if row else None

    def delete(self, task_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                self.sql("DELETE FROM tasks WHERE id = %s"),
                (task_id,),
            )
        return cursor.rowcount > 0

    def stats(self) -> dict[str, int]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN done THEN 1 ELSE 0 END), 0) AS done FROM tasks"
            ).fetchone()
            total, done = row.values() if isinstance(row, dict) else row
        return {"total": total, "done": done, "open": total - done}

    def reset(self) -> list[dict]:
        with self.connection() as connection:
            connection.execute("DELETE FROM tasks")
            if self.sqlite:
                connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("tasks",))
            else:
                connection.execute("ALTER SEQUENCE tasks_id_seq RESTART WITH 1")
            self.execute_many(
                connection,
                "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                SEED_TASKS,
            )
        return self.list_tasks()


repository = TaskRepository(os.environ.get("DATABASE_URL", "sqlite:///tasks.db"))
