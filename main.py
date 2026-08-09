from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator


load_dotenv()

from repository import repository
from auth_service import AuthError, auth_service


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A PostgreSQL-backed CRUD API for managing to-do tasks.",
)
bearer = HTTPBearer(auto_error=False)


class AccessError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code


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


class Credentials(BaseModel):
    email: str
    password: str

    @field_validator("email", "password")
    @classmethod
    def validate_credentials(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class RefreshToken(BaseModel):
    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("refresh_token must not be empty")
        return value


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


@app.exception_handler(AccessError)
async def handle_access_error(_, exc: AccessError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AccessError("Access token required")
    try:
        user = auth_service.user(credentials.credentials)
        return {**user, "_access_token": credentials.credentials}
    except AuthError as exc:
        if exc.status_code == 503:
            raise AccessError(exc.message, 503) from exc
        raise AccessError("Invalid or expired token") from exc


@app.get("/", tags=["System"])
def root() -> dict[str, str | list[str]]:
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok", "db": "ok" if repository.health() else "error"}


@app.post("/auth/signup", status_code=201, tags=["Authentication"])
def signup(payload: Credentials) -> dict:
    try:
        result = auth_service.signup(payload.email, payload.password)
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
    return result.get("user", result)


@app.post("/auth/login", tags=["Authentication"])
def login(payload: Credentials) -> dict:
    try:
        result = auth_service.login(payload.email, payload.password)
    except AuthError as exc:
        if exc.status_code == 503:
            return JSONResponse(status_code=503, content={"error": exc.message})
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid login credentials"},
        )
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
    }


@app.post("/auth/refresh", tags=["Authentication"])
def refresh(payload: RefreshToken) -> dict:
    try:
        result = auth_service.refresh(payload.refresh_token)
    except AuthError as exc:
        if exc.status_code == 503:
            return JSONResponse(status_code=503, content={"error": exc.message})
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid refresh token"},
        )
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
    }


@app.get("/public/info", tags=["Public"])
def public_info() -> dict[str, str]:
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile", tags=["Protected"])
def protected_profile(user: dict = Depends(current_user)) -> dict:
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "created_at": user.get("created_at"),
    }


@app.get("/protected/dashboard", tags=["Protected"])
def protected_dashboard(user: dict = Depends(current_user)) -> dict:
    return {"message": f"Welcome {user.get('email')}", "user_id": user.get("id")}


@app.get("/protected/admin", tags=["Protected"])
def protected_admin(user: dict = Depends(current_user)) -> dict:
    role = user.get("app_metadata", {}).get("role")
    if role != "admin":
        raise AccessError("Admin access required", 403)
    return {"message": "Welcome admin"}


@app.post("/auth/logout", status_code=204, tags=["Authentication"])
def logout(user: dict = Depends(current_user)) -> Response:
    try:
        auth_service.logout(user["_access_token"])
    except AuthError as exc:
        if exc.status_code == 503:
            raise AccessError(exc.message, 503) from exc
        raise AccessError("Invalid or expired token") from exc
    return Response(status_code=204)


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
