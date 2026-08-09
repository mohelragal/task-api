from typing import TypedDict

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator


app = FastAPI(
    title="Task API",
    version="1.0",
    description=(
        "A beginner-friendly in-memory CRUD API. Use **Try it out** to create, "
        "read, update, and delete tasks. Data resets when the server restarts."
    ),
    openapi_tags=[
        {"name": "System", "description": "API information and health checks."},
        {"name": "Tasks", "description": "Full CRUD operations for to-do tasks."},
    ],
)


class Task(TypedDict):
    id: int
    title: str
    done: bool


INITIAL_TASKS: list[Task] = [
    {"id": 1, "title": "Learn HTTP basics", "done": True},
    {"id": 2, "title": "Build a CRUD API", "done": False},
    {"id": 3, "title": "Test with Swagger UI", "done": False},
]
tasks: list[Task] = [task.copy() for task in INITIAL_TASKS]


class CreateTask(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


class UpdateTask(BaseModel):
    title: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    error = exc.errors()[0]
    field = str(error.get("loc", ["body"])[-1])
    message = str(error.get("msg", "Invalid request body"))
    return JSONResponse(status_code=400, content={"error": f"{field}: {message}"})


@app.get("/", summary="Describe the API", tags=["System"])
def root() -> dict[str, str | list[str]]:
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Check that the API is running", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks", summary="List all tasks", tags=["Tasks"])
def list_tasks(done: bool | None = None, search: str | None = None) -> list[Task]:
    """Optionally filter tasks by completion status and/or title text."""
    result = tasks
    if done is not None:
        result = [task for task in result if task["done"] is done]
    if search:
        query = search.casefold()
        result = [task for task in result if query in task["title"].casefold()]
    return result


@app.get(
    "/tasks/{task_id}", summary="Get one task", tags=["Tasks"], response_model=None
)
def get_task(task_id: int) -> Task | JSONResponse:
    task = next((item for item in tasks if item["id"] == task_id), None)
    if task is None:
        return JSONResponse(
            status_code=404, content={"error": f"Task {task_id} not found"}
        )
    return task


@app.post("/tasks", status_code=201, summary="Create a task", tags=["Tasks"])
def create_task(payload: CreateTask) -> Task:
    next_id = max((task["id"] for task in tasks), default=0) + 1
    task: Task = {"id": next_id, "title": payload.title, "done": False}
    tasks.append(task)
    return task


@app.put(
    "/tasks/{task_id}", summary="Update a task", tags=["Tasks"], response_model=None
)
def update_task(task_id: int, payload: UpdateTask) -> Task | JSONResponse:
    task = next((item for item in tasks if item["id"] == task_id), None)
    if task is None:
        return JSONResponse(
            status_code=404, content={"error": f"Task {task_id} not found"}
        )
    if not payload.model_fields_set:
        return JSONResponse(
            status_code=400,
            content={"error": "Request body must include title and/or done"},
        )
    if "title" in payload.model_fields_set:
        assert payload.title is not None
        task["title"] = payload.title
    if "done" in payload.model_fields_set:
        if payload.done is None:
            return JSONResponse(
                status_code=400, content={"error": "done must be true or false"}
            )
        task["done"] = payload.done
    return task


@app.delete(
    "/tasks/{task_id}", status_code=204, summary="Delete a task", tags=["Tasks"]
)
def delete_task(task_id: int) -> Response:
    index = next(
        (position for position, item in enumerate(tasks) if item["id"] == task_id),
        None,
    )
    if index is None:
        return JSONResponse(
            status_code=404, content={"error": f"Task {task_id} not found"}
        )
    tasks.pop(index)
    return Response(status_code=204)


@app.get("/stats", summary="Show task totals", tags=["Tasks"])
def task_stats() -> dict[str, int]:
    done_count = sum(task["done"] for task in tasks)
    return {"total": len(tasks), "done": done_count, "open": len(tasks) - done_count}


@app.post("/reset", summary="Restore the example tasks", tags=["Tasks"])
def reset_tasks() -> list[Task]:
    tasks[:] = [task.copy() for task in INITIAL_TASKS]
    return tasks
