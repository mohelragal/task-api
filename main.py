from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator


load_dotenv()

from repository import repository


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A PostgreSQL-backed CRUD API for managing to-do tasks.",
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


repository.initialize()


def not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "Task not found"})


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
    return {"status": "ok", "db": "ok" if repository.health() else "error"}


@app.get("/tasks", response_model=list[Task], tags=["Tasks"])
def list_tasks(done: bool | None = None, search: str | None = None) -> list[dict]:
    return repository.list_tasks(done, search)


@app.get("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def get_task(task_id: int) -> dict | Response:
    return repository.get(task_id) or not_found()


@app.post("/tasks", response_model=Task, status_code=201, tags=["Tasks"])
def create_task(payload: TaskCreate) -> dict:
    return repository.create(payload.title)


@app.put("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def update_task(task_id: int, payload: TaskUpdate) -> dict | Response:
    task = repository.get(task_id)
    if task is None:
        return not_found()
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
    title = payload.title if "title" in payload.model_fields_set else task["title"]
    done = payload.done if "done" in payload.model_fields_set else task["done"]
    return repository.update(task_id, title, done)


@app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
def delete_task(task_id: int) -> Response:
    if not repository.delete(task_id):
        return not_found()
    return Response(status_code=204)


@app.get("/stats", tags=["Tasks"])
def task_stats() -> dict[str, int]:
    return repository.stats()


@app.post("/reset", response_model=list[Task], tags=["Tasks"])
def reset_tasks() -> list[dict]:
    return repository.reset()
