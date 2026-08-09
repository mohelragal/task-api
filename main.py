from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator


app = FastAPI(
    title="Task API",
    version="1.0",
    description="An in-memory CRUD API for managing to-do tasks.",
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


SEED_TASKS = [
    Task(id=1, title="Learn HTTP basics", done=True),
    Task(id=2, title="Build a CRUD API"),
    Task(id=3, title="Test with Swagger UI"),
]
tasks = [task.model_copy() for task in SEED_TASKS]


def find_task(task_id: int) -> Task | None:
    return next((task for task in tasks if task.id == task_id), None)


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
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
    result = tasks
    if done is not None:
        result = [task for task in result if task.done is done]
    if search:
        query = search.casefold()
        result = [task for task in result if query in task.title.casefold()]
    return result


@app.get("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def get_task(task_id: int) -> Task | Response:
    return find_task(task_id) or not_found(task_id)


@app.post("/tasks", response_model=Task, status_code=201, tags=["Tasks"])
def create_task(payload: TaskCreate) -> Task:
    task = Task(
        id=max((task.id for task in tasks), default=0) + 1,
        title=payload.title,
    )
    tasks.append(task)
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
    if "title" in payload.model_fields_set:
        task.title = payload.title
    if "done" in payload.model_fields_set:
        if payload.done is None:
            return JSONResponse(
                status_code=400,
                content={"error": "done must be true or false"},
            )
        task.done = payload.done
    return task


@app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
def delete_task(task_id: int) -> Response:
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    tasks.remove(task)
    return Response(status_code=204)


@app.get("/stats", tags=["Tasks"])
def task_stats() -> dict[str, int]:
    done = sum(task.done for task in tasks)
    return {"total": len(tasks), "done": done, "open": len(tasks) - done}


@app.post("/reset", response_model=list[Task], tags=["Tasks"])
def reset_tasks() -> list[Task]:
    tasks[:] = [task.model_copy() for task in SEED_TASKS]
    return tasks
