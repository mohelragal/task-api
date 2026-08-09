import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, field_validator


app = FastAPI(title="AI SQLite Task API")
database = Path("ai_tasks.db")
seeds = [
    ("Learn HTTP basics", 1),
    ("Build a CRUD API", 0),
    ("Test with Swagger UI", 0),
]


class TaskInput(BaseModel):
    title: str
    done: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


def connection() -> sqlite3.Connection:
    value = sqlite3.connect(database)
    value.row_factory = sqlite3.Row
    return value


def setup() -> None:
    with closing(connection()) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)"
        )
        if db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
            db.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", seeds)
        db.commit()


def read_task(task_id: int) -> dict:
    with closing(connection()) as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "Task not found"})
    return dict(row)


setup()


@app.get("/tasks")
def list_tasks() -> list[dict]:
    with closing(connection()) as db:
        return [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY id")]


@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> dict:
    return read_task(task_id)


@app.post("/tasks", status_code=201)
def create_task(payload: TaskInput) -> dict:
    with closing(connection()) as db:
        cursor = db.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (payload.title, int(payload.done)),
        )
        db.commit()
    return read_task(cursor.lastrowid)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskInput) -> dict:
    read_task(task_id)
    with closing(connection()) as db:
        db.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (payload.title, int(payload.done), task_id),
        )
        db.commit()
    return read_task(task_id)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int) -> Response:
    read_task(task_id)
    with closing(connection()) as db:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
    return Response(status_code=204)
