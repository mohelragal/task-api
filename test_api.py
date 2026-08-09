from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def reset() -> None:
    response = client.post("/reset")
    assert response.status_code == 200


def test_system_endpoints_and_docs() -> None:
    assert client.get("/").json() == {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_complete_crud_cycle() -> None:
    reset()

    created = client.post("/tasks", json={"title": "Buy milk"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json() == {"id": task_id, "title": "Buy milk", "done": False}

    fetched = client.get(f"/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()

    updated = client.put(
        f"/tasks/{task_id}", json={"title": "Buy oat milk", "done": True}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Buy oat milk"
    assert updated.json()["done"] is True

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_validation_and_not_found_errors() -> None:
    reset()
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "   "}).status_code == 400
    assert client.put("/tasks/1", json={}).status_code == 400
    assert client.get("/tasks/99").json() == {"error": "Task 99 not found"}
    assert client.put("/tasks/99", json={"done": True}).status_code == 404
    assert client.delete("/tasks/99").status_code == 404


def test_extras() -> None:
    reset()
    assert all(task["done"] for task in client.get("/tasks?done=true").json())
    search_results = client.get("/tasks?search=swagger").json()
    assert len(search_results) == 1
    assert "Swagger" in search_results[0]["title"]
    assert client.get("/stats").json() == {"total": 3, "done": 1, "open": 2}
