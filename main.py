import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A SQLite-backed CRUD API for managing to-do tasks.",
)


class Task(BaseModel):
    id: int
    title: str
    done: bool = False


class TaskCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str) -> str:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        return title


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str | None) -> str:
        if title is None or not title.strip():
            raise ValueError("title must not be empty")
        return title.strip()


DATABASE_PATH = Path("tasks.db")
SEED_TASKS = [
    Task(id=1, title="Learn HTTP basics", done=True),
    Task(id=2, title="Build a CRUD API"),
    Task(id=3, title="Test with Swagger UI"),
]


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)"
        )
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            connection.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                [(task.title, int(task.done)) for task in SEED_TASKS],
            )


initialize_database()


def find_task(task_id: int) -> Task | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return Task(**dict(row)) if row else None


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "Task not found"},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_, exc: RequestValidationError) -> JSONResponse:
    error = exc.errors()[0]
    field = str(error.get("loc", ["body"])[-1])
    return JSONResponse(
        status_code=400,
        content={"error": f"{field}: {error['msg']}"},
    )


@app.get("/", tags=["System"])
def root() -> dict[str, str | list[str]]:
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], tags=["Tasks"])
def list_tasks(done: bool | None = None, search: str | None = None) -> list[Task]:
    clauses = []
    parameters = []
    if done is not None:
        clauses.append("done = ?")
        parameters.append(int(done))
    if search:
        clauses.append("title LIKE ?")
        parameters.append(f"%{search}%")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            f"SELECT id, title, done FROM tasks{where} ORDER BY id",
            parameters,
        ).fetchall()
    return [Task(**dict(row)) for row in rows]


@app.get("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def get_task(task_id: int) -> Task | Response:
    return find_task(task_id) or not_found(task_id)


@app.post("/tasks", response_model=Task, status_code=201, tags=["Tasks"])
def create_task(payload: TaskCreate) -> Task:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (payload.title, 0),
        )
    task = find_task(cursor.lastrowid)
    assert task is not None
    return task


@app.put("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def update_task(task_id: int, payload: TaskUpdate) -> Task | Response:
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    if not payload.model_fields_set:
        return JSONResponse(
            status_code=400,
            content={"error": "Body must include title and/or done"},
        )
    if "done" in payload.model_fields_set and payload.done is None:
        return JSONResponse(
            status_code=400,
            content={"error": "done must be true or false"},
        )
    title = payload.title if "title" in payload.model_fields_set else task.title
    done = payload.done if "done" in payload.model_fields_set else task.done
    with connect() as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (title, int(done), task_id),
        )
    updated = find_task(task_id)
    assert updated is not None
    return updated


@app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
def delete_task(task_id: int) -> Response:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cursor.rowcount == 0:
        return not_found(task_id)
    return Response(status_code=204)


@app.get("/stats", tags=["Tasks"])
def task_stats() -> dict[str, int]:
    with connect() as connection:
        total, done = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(done), 0) FROM tasks"
        ).fetchone()
    return {"total": total, "done": done, "open": total - done}


@app.post("/reset", response_model=list[Task], tags=["Tasks"])
def reset_tasks() -> list[Task]:
    with connect() as connection:
        connection.execute("DELETE FROM tasks")
        connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("tasks",))
        connection.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            [(task.title, int(task.done)) for task in SEED_TASKS],
        )
    return list_tasks()
