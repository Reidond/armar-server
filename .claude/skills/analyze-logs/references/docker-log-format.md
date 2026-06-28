# Docker Compose Log Format Reference

## Log Line Structure

### Multi-container output (`docker compose logs`)

```
container-name-1  | 2026-03-21 10:15:23.456 INFO:     uvicorn.access: 192.168.1.1:0 - "GET /api/v1/health HTTP/1.1" 200
container-name-1  | 2026-03-21 10:15:24.789 ERROR:    app.services.interview: Failed to process audio chunk
container-name-1  | Traceback (most recent call last):
container-name-1  |   File "/app/src/services/interview/audio_processor.py", line 42, in process
container-name-1  |     result = await self._client.transcribe(chunk)
container-name-1  | openai.APIError: Request timed out
```

**Parsing rules:**
- Container name prefix ends at ` | ` (pipe with surrounding spaces)
- Everything after the pipe is the actual log content
- Multi-line entries (stack traces) share the same container prefix
- Container names may have a numeric suffix (`-1`, `-2`) for scaled services

### Single-container output (`docker compose logs backend`)

Same format but all lines share one container prefix. Can also appear without prefix
if captured via `docker logs <container-id>`.

## Severity Detection

Docker logs don't have a structured severity field. Detect from the log line content:

| Pattern | Severity | Examples |
|---------|----------|----------|
| `ERROR:` or `ERROR ` | ERROR | `ERROR:    app.core.middleware: Unhandled exception` |
| `WARNING:` or `WARNING ` | WARNING | `WARNING:  app.services.coach: Session timeout approaching` |
| `INFO:` or `INFO ` | INFO | `INFO:     uvicorn.access: ...` |
| `DEBUG:` or `DEBUG ` | DEBUG | `DEBUG:    app.core.logging: Request context set` |
| `CRITICAL:` | CRITICAL | `CRITICAL: app.core.config: Missing required env var` |
| `Traceback (most recent call last):` | ERROR (continuation) | Stack trace follows a preceding ERROR line |
| HTTP status 5xx in access log | ERROR | `"POST /api/v1/interview HTTP/1.1" 500` |
| HTTP status 4xx in access log | WARNING | `"GET /api/v1/user HTTP/1.1" 401` |

## Timestamp Formats

| Source | Format | Example |
|--------|--------|---------|
| Python logging | `YYYY-MM-DD HH:MM:SS.mmm` | `2026-03-21 10:15:23.456` |
| Uvicorn access | `YYYY-MM-DD HH:MM:SS.mmm` | Same |
| Docker daemon | `YYYY-MM-DDTHH:MM:SS.nnnnnnnnnZ` | `2026-03-21T10:15:23.456789000Z` |
| Alembic/startup | May lack timestamps | `INFO  [alembic.runtime.migration] Running upgrade...` |

## Request Correlation

Docker logs lack GCP's trace/span fields. Correlate requests using:

1. **Request ID** — look for `request_id=` or `X-Request-ID` in log messages
2. **Context fields** — `user_id=`, `interview_id=`, `session_id=`, `coach_session_id=` set via `set_logging_context()`
3. **Temporal grouping** — entries within the same second from the same container, sharing a module path
4. **Uvicorn access log pairing** — match the request start (`INFO: ... "POST /path"`) with preceding application logs by timestamp

## Container Names (Project project)

| Container | Typical Name | What It Runs |
|-----------|-------------|--------------|
| Backend API | `backend-1` or `upstream-backend-1` | FastAPI app (uvicorn) |
| Database | `db-1` or `postgres-1` | PostgreSQL |
| Redis | `redis-1` | Redis cache |
| Test runner | `test-runner-fast-1` | Pytest in container |

## Stack Trace Parsing

Python tracebacks in Docker logs are identical to GCP, but each line is prefixed with the container name:

```
backend-1  | Traceback (most recent call last):
backend-1  |   File "/app/src/features/interview/services/session_handler.py", line 156, in handle_audio
backend-1  |     await self._audio_processor.process(chunk)
backend-1  |   File "/app/src/features/interview/services/audio_processor.py", line 42, in process
backend-1  |     result = await self._client.transcribe(chunk)
backend-1  | openai.APITimeoutError: Request timed out
```

**Path mapping:** Container paths start with `/app/` which maps to the repository root.
- `/app/src/features/...` → `src/features/...`
- `/app/alembic/...` → `alembic/...`

## Docker-Specific Issue Patterns

| Pattern | What It Means |
|---------|---------------|
| `Connection refused` on startup | Container started before dependency (DB, Redis) was ready |
| `OSError: [Errno 98] Address already in use` | Port conflict — previous container didn't shut down cleanly |
| `sqlalchemy.exc.OperationalError: connection to server closed` | DB connection pool exhaustion or container restart |
| Repeated `health check` failures | App not responding — check startup errors above |
| `ModuleNotFoundError` | Missing dependency — `uv sync` or Dockerfile issue |
| `alembic.util.exc.CommandError` | Migration conflict or missing migration |
