import os
from typing import Any

import httpx


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code


class SupabaseAuth:
    def __init__(self) -> None:
        self.url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_KEY", "")

    def headers(self, token: str | None = None) -> dict[str, str]:
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        if not self.url or not self.key:
            raise AuthError("Authentication service is not configured", 503)
        try:
            response = httpx.request(
                method,
                f"{self.url}/auth/v1/{path}",
                headers=self.headers(token),
                json=payload,
                timeout=10,
            )
        except httpx.RequestError as exc:
            raise AuthError("Authentication service unavailable", 503) from exc
        if response.is_error:
            message = response.json().get("msg") or response.json().get("message")
            raise AuthError(message or "Authentication request failed", response.status_code)
        return response.json() if response.content else {}

    def signup(self, email: str, password: str) -> dict[str, Any]:
        return self.request("POST", "signup", {"email": email, "password": password})

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "token?grant_type=password",
            {"email": email, "password": password},
        )

    def user(self, token: str) -> dict[str, Any]:
        return self.request("GET", "user", token=token)

    def logout(self, token: str) -> None:
        self.request("POST", "logout", token=token)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "token?grant_type=refresh_token",
            {"refresh_token": refresh_token},
        )


auth_service = SupabaseAuth()
