# Task API

A small in-memory CRUD API for to-do tasks, built with Python and FastAPI for the FlyRank Backend Track Week 2 assignment.

## Run locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the environment:

- Windows: `.venv\Scripts\activate`
- macOS/Linux: `source .venv/bin/activate`

Install and start the API:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open <http://localhost:8000/docs> for interactive Swagger UI.

## Endpoints

| Method | Path | Success | Description |
|---|---|---:|---|
| GET | `/` | 200 | Describe the API |
| GET | `/health` | 200 | Health check |
| GET | `/tasks` | 200 | List tasks; supports `done` and `search` filters |
| GET | `/tasks/{task_id}` | 200 | Get one task |
| POST | `/tasks` | 201 | Create a task |
| PUT | `/tasks/{task_id}` | 200 | Update a task's `title` and/or `done` value |
| DELETE | `/tasks/{task_id}` | 204 | Delete a task |
| GET | `/stats` | 200 | Return total, done, and open counts |
| POST | `/reset` | 200 | Restore the three example tasks |

Invalid request bodies return `400`. Unknown task IDs return `404`. Errors are JSON objects with an `error` message.

## Example request

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy milk"}'
```

```text
HTTP/1.1 201 Created
date: Sun, 09 Aug 2026 00:00:00 GMT
server: uvicorn
content-length: 40
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

## Swagger UI

![Task API Swagger UI](images/swagger-ui.png)

## Test

Install the test packages and run the suite:

```bash
pip install -r requirements-dev.txt
pytest -q
```

The tests cover the full CRUD cycle, status codes, validation, error messages, Swagger/OpenAPI availability, filters, stats, and reset.

## Why tasks disappear after a restart

Tasks are stored only in the Python process's memory. Stopping the server clears that memory, so the three seed tasks return the next time the app starts; a database will provide persistence in a later version.

## Publish to GitHub

Create an empty public GitHub repository, then run:

```bash
git remote add origin https://github.com/YOUR-USERNAME/task-api.git
git push -u origin main
```

The local repository already contains meaningful commits for Stages 0 through 5, the extras, tests, and documentation.

## AI vs me - Stage 7

The comparison implementation is isolated in [`ai-version/`](ai-version/), so it does not replace the main submission.

### Original prompt

> Build a Python 3.10+ FastAPI application for an in-memory to-do list. Include GET /, GET /health, GET /tasks, GET /tasks/{id}, POST /tasks, PUT /tasks/{id}, and DELETE /tasks/{id}. Every task has an integer id, a non-empty string title, and a boolean done value. Seed three example tasks. POST assigns the next id and returns 201; DELETE returns an empty 204 response. Reads and updates return 200. Missing tasks return 404 with `{"error":"Task <id> not found"}`. Missing, empty, or invalid POST and PUT bodies return 400 with a JSON error. PUT may change title, done, or both. Keep all data in memory and expose clear Swagger documentation at /docs. Put everything in one main.py file and do not add a database.

### Three concrete differences

1. **The AI version models stored tasks with Pydantic.** This produces stronger response schemas in Swagger and rejects unexpected fields. The main version uses a `TypedDict`, which is simpler for a first assignment.
2. **The AI version centralizes lookup in `find_task`.** That removes repeated search code, but FastAPI's default `HTTPException` wraps its message as `{"detail": ...}`. The main version deliberately returns `{"error": ...}`, matching the assignment exactly.
3. **The main version includes extras the prompt omitted.** Filtering, title search, `/stats`, and `/reset` are present only in the main implementation because the AI prompt described the required CRUD API but forgot the optional features.

### What the AI did better

Its `Task`, `TaskCreate`, and `TaskUpdate` models make the data contract explicit and produce richer OpenAPI schemas. The shared lookup helper also avoids duplication.

### What it got wrong or ignored

It returned missing-task errors under the key `detail` rather than the requested `error` key. It also did not add filtering, statistics, or reset because those extras were absent from the prompt.

### What the prompt silently left open

The prompt did not say whether unknown request fields should be accepted. The AI chose strict models with `extra="forbid"`; the main version uses FastAPI's normal permissive behavior.

### Rematch

For a second prompt, I would explicitly require the exact error shape for every route, list the optional endpoints, and state whether extra JSON fields must be rejected. Those additions remove the three silent choices found in the first result.
