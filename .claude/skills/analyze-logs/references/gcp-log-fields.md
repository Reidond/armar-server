# GCP Structured Log Fields Reference

## Primary Fields

| Field | Type | Description | Analysis Use |
|-------|------|-------------|--------------|
| `severity` | string | `DEBUG`, `INFO`, `NOTICE`, `WARNING`, `ERROR`, `CRITICAL`, `ALERT`, `EMERGENCY` | Issue identification, priority sorting |
| `timestamp` | string | RFC 3339 timestamp | Timeline reconstruction, correlation |
| `textPayload` | string | Unstructured log message (plain text) | Error messages, stack traces |
| `jsonPayload` | object | Structured log data | Parsed error details, context fields |
| `jsonPayload.message` | string | Log message within structured payload | Primary error text |
| `jsonPayload.severity` | string | Application-level severity (may differ from top-level) | Cross-reference with top-level severity |
| `insertId` | string | Unique entry ID | Deduplication |
| `trace` | string | `projects/{project}/traces/{trace_id}` | Request correlation across entries |
| `spanId` | string | Span within a trace | Sub-operation correlation |
| `resource` | object | Source resource metadata | Service identification |

## Resource Labels

| Field | Description |
|-------|-------------|
| `resource.type` | e.g., `cloud_run_revision`, `k8s_container` |
| `resource.labels.service_name` | Cloud Run service name |
| `resource.labels.revision_name` | Deployment revision |
| `resource.labels.location` | GCP region |
| `resource.labels.project_id` | GCP project ID |
| `resource.labels.configuration_name` | Service configuration |

## HTTP Request Fields

| Field | Description |
|-------|-------------|
| `httpRequest.requestMethod` | GET, POST, PUT, DELETE, etc. |
| `httpRequest.requestUrl` | Full request URL |
| `httpRequest.status` | HTTP response status code |
| `httpRequest.latency` | Request duration (e.g., `0.234s`) |
| `httpRequest.userAgent` | Client user agent |
| `httpRequest.remoteIp` | Client IP |
| `httpRequest.responseSize` | Response body size in bytes |

## Application Context Fields (Project-specific)

These appear in `jsonPayload` when set via `set_logging_context()`:

| Field | Description |
|-------|-------------|
| `user_id` | Authenticated user ID |
| `interview_id` | ExampleEntity session ID |
| `session_id` | WebSocket/HTTP session ID |
| `coach_session_id` | Coach test session ID |
| `request_id` | X-Request-ID header value |
| `event_type` | Application event classifier (from `log_event()`) |

## Parsing Tips

- **Stack traces** are typically in `textPayload` or `jsonPayload.message` as multi-line strings.
- **Python tracebacks** start with `Traceback (most recent call last):` and end with the exception line.
- **Multiple payloads**: an entry has EITHER `textPayload` OR `jsonPayload`, never both.
- **Trace correlation**: strip the `projects/{project}/traces/` prefix to get the raw trace ID for grouping.
- **Latency parsing**: `httpRequest.latency` is a string like `"0.234s"` — parse the float for comparison.
