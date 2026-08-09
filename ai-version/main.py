from typing import Annotated

from fastapi import FastAPI, HTTPException, Path
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator


app = FastAPI(
    title="AI Task API",
    version="1.0",
    description="An AI-generated comparison implementation of the Task CRUD API.",
)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be empty")
        return value.strip() if value is not None else None


tasks = [
    Task(id=1, title="Learn HTTP basics", done=True),
    Task(id=2, title="Build a CRUD API", done=False),
    Task(id=3, title="Test with Swagger UI", done=False),
]


@app.exception_handler(RequestValidationError)
async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": exc.errors()[0]["msg"]})


def find_task(task_id: int) -> Task:
    task = next((item for item in tasks if item.id == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.get("/", summary="Describe the API")
def root() -> dict[str, str | list[str]]:
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Check API health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], summary="List all tasks")
def list_tasks() -> list[Task]:
    return tasks


@app.get("/tasks/{task_id}", response_model=Task, summary="Get one task")
def get_task(task_id: Annotated[int, Path(ge=1)]) -> Task:
    return find_task(task_id)


@app.post("/tasks", response_model=Task, status_code=201, summary="Create a task")
def create_task(payload: TaskCreate) -> Task:
    next_id = max((task.id for task in tasks), default=0) + 1
    task = Task(id=next_id, title=payload.title, done=False)
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task, summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = find_task(task_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Body must include title and/or done")
    for field, value in changes.items():
        setattr(task, field, value)
    return task


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int) -> Response:
    task = find_task(task_id)
    tasks.remove(task)
    return Response(status_code=204)
