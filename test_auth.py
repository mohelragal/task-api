from fastapi.testclient import TestClient

from auth_service import AuthError
from main import app, auth_service


client = TestClient(app)


def user() -> dict:
    return {
        "id": "user-123",
        "email": "test@example.com",
        "created_at": "2026-08-09T00:00:00Z",
    }


def test_signup_and_login(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "signup", lambda email, password: {"user": user()})
    monkeypatch.setattr(
        auth_service,
        "login",
        lambda email, password: {
            "access_token": "valid-token",
            "refresh_token": "refresh-token",
        },
    )
    signup = client.post(
        "/auth/signup",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == "test@example.com"
    login = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json() == {
        "access_token": "valid-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
    }


def test_auth_validation_and_invalid_login(monkeypatch) -> None:
    assert client.post("/auth/signup", json={"email": "test@example.com"}).status_code == 400
    assert client.post("/auth/login", json={"email": "", "password": "x"}).status_code == 400

    def invalid(email, password):
        raise AuthError("provider detail", 400)

    monkeypatch.setattr(auth_service, "login", invalid)
    response = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid login credentials"}


def test_public_and_protected_routes(monkeypatch) -> None:
    assert client.get("/public/info").json() == {
        "message": "Welcome stranger! This info is public."
    }
    assert client.get("/protected/profile").json() == {
        "error": "Access token required"
    }
    assert client.get(
        "/protected/profile", headers={"Authorization": "Token invalid"}
    ).status_code == 401

    def verify(token):
        if token != "valid-token":
            raise AuthError("invalid", 401)
        return user()

    monkeypatch.setattr(auth_service, "user", verify)
    invalid = client.get(
        "/protected/profile", headers={"Authorization": "Bearer tampered"}
    )
    assert invalid.status_code == 401
    assert invalid.json() == {"error": "Invalid or expired token"}
    headers = {"Authorization": "Bearer valid-token"}
    assert client.get("/protected/profile", headers=headers).json() == user()
    assert client.get("/protected/dashboard", headers=headers).status_code == 200


def test_logout_and_swagger_security(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "user", lambda token: user())
    logged_out = []
    monkeypatch.setattr(auth_service, "logout", lambda token: logged_out.append(token))
    response = client.post(
        "/auth/logout", headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 204
    assert response.content == b""
    assert logged_out == ["valid-token"]
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert schema["paths"]["/protected/profile"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]


def test_refresh_and_admin_authorization(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service,
        "refresh",
        lambda token: {
            "access_token": "fresh-token",
            "refresh_token": "next-refresh-token",
        },
    )
    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": "refresh-token"}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] == "fresh-token"
    monkeypatch.setattr(auth_service, "user", lambda token: user())
    denied = client.get(
        "/protected/admin", headers={"Authorization": "Bearer valid-token"}
    )
    assert denied.status_code == 403
    assert denied.json() == {"error": "Admin access required"}
    admin = {**user(), "app_metadata": {"role": "admin"}}
    monkeypatch.setattr(auth_service, "user", lambda token: admin)
    allowed = client.get(
        "/protected/admin", headers={"Authorization": "Bearer valid-token"}
    )
    assert allowed.status_code == 200
