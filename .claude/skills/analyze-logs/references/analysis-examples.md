# Analysis Quality Examples

## Good vs. Bad Root Cause Analysis

### Example 1: Database Connection Error

**Log excerpt:**
```
ERROR: app.features.{feature}.storage.interview_repository: Failed to save transcript
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) server closed the connection unexpectedly
```

**BAD analysis (surface-level):**
> Root Cause: The database connection was closed. The fix is to add retry logic.

Why this is bad: describes the symptom, not the cause. Doesn't explain WHY the connection was closed or reference any code.

**GOOD analysis (evidence-based):**
> Root Cause: The `InterviewRepository.save_transcript()` at `src/features/interview/storage/interview_repository.py:87` uses a long-running session that spans the entire interview WebSocket lifecycle. When an interview exceeds the PostgreSQL `idle_in_transaction_session_timeout` (default: 30 minutes in our `docker-compose.local.yaml`), the server drops the connection. The repository acquires a session in `__init__` but only commits at interview end, leaving the transaction idle during the entire audio exchange.
>
> Evidence:
> - `interview_repository.py:23` — session injected via `__init__`, not per-operation
> - `docker-compose.local.yaml:45` — PostgreSQL `idle_in_transaction_session_timeout=1800000`
> - Log timing: error occurs ~31 minutes after interview start (10:15:23 start, 10:46:45 error)

---

### Example 2: Hypothesis Labeling

**Log excerpt:**
```
WARNING: app.features.coach_test.services.voice_test_session: Audio buffer overflow, dropping 3 chunks
WARNING: app.features.coach_test.services.voice_test_session: Audio buffer overflow, dropping 5 chunks
ERROR:   app.features.coach_test.services.voice_test_session: Session terminated unexpectedly
```

**BAD analysis (unfounded speculation):**
> Root Cause: The audio processing is too slow and can't keep up with the input stream, probably because the OpenAI API is rate-limiting us.

Why this is bad: "probably" hides a guess as a conclusion. No code reference, no evidence for rate limiting.

**GOOD analysis (properly labeled hypothesis):**
> Root Cause: The `VoiceTestSession._process_audio_queue()` at `src/features/coach_test/services/voice_test_session.py:134` drops chunks when the internal buffer exceeds `MAX_BUFFER_SIZE=50`. After dropping 8+ chunks (logged warnings), the session receives an incomplete audio segment that causes the OpenAI Realtime API to return an error, triggering session termination at line 201.
>
> Evidence:
> - `voice_test_session.py:134` — buffer overflow threshold and drop logic confirmed
> - `voice_test_session.py:201` — termination on API error confirmed
> - Log sequence: 2 buffer overflow warnings precede the termination error by <1 second
>
> [HYPOTHESIS] The buffer overflow itself may be caused by either: (a) network latency spikes to OpenAI slowing the consumer, or (b) the client sending audio faster than real-time. Evidence needed: check if `httpRequest.latency` for OpenAI calls spikes before the overflow warnings, or compare audio chunk timestamps against wall-clock time.

---

### Example 3: Issue Grouping

**Log entries (within 2 seconds):**
```
10:15:23.100 ERROR: app.features.{feature}.services.feedback_generator: Failed to generate feedback for interview abc-123
10:15:23.150 ERROR: app.core.api.middleware.unified: Unhandled exception in POST /api/v1/interviews/abc-123/feedback
10:15:24.200 ERROR: app.features.{feature}.services.feedback_generator: Failed to generate feedback for interview def-456
10:15:24.250 ERROR: app.core.api.middleware.unified: Unhandled exception in POST /api/v1/interviews/def-456/feedback
```

**BAD grouping (over-split):**
> Issue 1: Feedback generation failed for interview abc-123
> Issue 2: Unhandled exception in middleware for abc-123
> Issue 3: Feedback generation failed for interview def-456
> Issue 4: Unhandled exception in middleware for def-456

Why this is bad: 4 "issues" that are really 1. The middleware errors are just the service error bubbling up. Both interviews hit the same bug.

**GOOD grouping:**
> Issue 1: Feedback generation failure — 2 occurrences (abc-123, def-456)
>
> The middleware errors are the service exception propagating through the error handling chain, not a separate problem. Both interviews fail with the same exception in `feedback_generator.py`, indicating a systematic issue (not interview-specific).
