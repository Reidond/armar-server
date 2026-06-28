# Realtime Session Event Vocabulary

## Overview

The project backend manages OpenAI Realtime API sessions for interviews and coach tests.
Logs from these sessions use specific `event_type` values in `jsonPayload` that require
domain-specific analysis. This reference covers event patterns, timing analysis, and
known failure modes.

## Event Types — Session Lifecycle

| event_type | Meaning | Key Fields |
|------------|---------|------------|
| `session_started` | OpenAI realtime session established | `session_id`, `model` |
| `session_configured` | Session parameters sent to OpenAI | `turn_detection_type`, `silence_duration_ms` |
| `session_ended` | Session closed (normal or error) | `reason`, `duration_seconds` |
| `connection_established` | WebSocket to client connected | `session_id`, `user_id` |
| `connection_closed` | WebSocket to client disconnected | `reason`, `duration_seconds` |
| `connection_quality_failed` | Ping/health check failure | `quality`, `error_count`, `rtt_ms` |
| `ping_failed` | Individual ping failure | `error` |
| `ping_failure_cascade` | Multiple consecutive ping failures, forced disconnect | `consecutive_failures` |

## Event Types — Conversation Flow

| event_type | Meaning | Key Fields |
|------------|---------|------------|
| `speech_started` | User began speaking (VAD detected) | `has_active_response` (critical for interruption analysis) |
| `speech_stopped` | User stopped speaking (VAD detected) | `speech_duration_ms` |
| `turn_started` | Conversation turn began | `role` (user/assistant), `turn_number` |
| `turn_completed` | Conversation turn ended | `role`, `turn_number`, `duration_seconds`, `text_length` |
| `response_created` | AI response generation started | `response_id` |
| `response_completed` | AI response generation finished | `response_id`, `response_length` |
| `barge_in_truncate_decision` | OpenAI server-side barge-in (WARNING) | User spoke while AI was responding |
| `user_transcript` | User speech transcribed | `text`, `text_length` |

## Event Types — Audio

| event_type | Meaning | Key Fields |
|------------|---------|------------|
| `audio_stream_started` | Audio streaming began | |
| `audio_stream_ended` | Audio streaming ended | |
| `audio_storage_complete` | Audio files saved | `user_bytes`, `assistant_bytes` |
| `transcript_save` | Transcripts persisted | `count` |

## Event Types — ExampleEntity Lifecycle

| event_type | Meaning | Key Fields |
|------------|---------|------------|
| `interview_started` | ExampleEntity session began | `interview_id`, `user_id`, `interview_type` |
| `interview_completed` | ExampleEntity session ended | `duration_seconds`, `questions_count`, `completion_percentage` |
| `feedback_generation_started` | Feedback pipeline triggered | `interview_id` |
| `feedback_generation_completed` | Feedback pipeline finished | `overall_score`, `duration_seconds` |

## Interruption Analysis Protocol

When investigating "AI interrupts user" reports, follow this sequence:

### 1. Reconstruct Turn Timeline

For each session, build a chronological timeline of these events:
```
speech_started → speech_stopped → user_transcript → turn_started(assistant) → response_created → response_completed → turn_completed(assistant)
```

Normal flow: `speech_stopped` happens, then after silence_duration_ms, `turn_started(assistant)`.
Interruption: `response_created` immediately followed by `speech_started` with `has_active_response=true`.

### 2. Measure Critical Timing Gaps

| Gap | Normal Range | Anomaly Signal |
|-----|-------------|----------------|
| `speech_stopped` → `response_created` | >silence_duration_ms (typically 3000ms) | If significantly shorter, VAD config may not match |
| `response_created` → `speech_started` | >500ms (human reaction) | **<100ms = user was already speaking = false end-of-turn** |
| `turn_started(assistant)` → `turn_completed(assistant)` | 2-30s | <1s = response was truncated |
| `speech_stopped` → next `speech_started` | varies | If another speech segment starts within silence_duration_ms, the user was pausing mid-thought |

### 3. Detect False End-of-Turn Patterns

Signs of VAD false positives:
- **Sub-10ms gap** between `response_created` and `speech_started` = user never stopped speaking
- **Very short transcripts** (<20 chars) from long speech durations (>5s) = speech was split by VAD
- **`barge_in_truncate_decision` warnings** shortly after `response_created` = OpenAI detected collision
- **Short assistant turn duration** (<1s) followed by long user speech = AI was immediately cut off
- **Consecutive user turns** with short transcripts = single utterance fragmented by VAD

### 4. Check Configuration Verification

Look for these log entries to verify what was actually sent to OpenAI:
- `session_configured` or `session.update` events showing turn_detection parameters
- If absent, flag as **observability gap** — the config may not match what's in code

### 5. Cross-Session Pattern Detection

Compare the same metrics across all sessions in the log file:
- Does the same user experience more interruptions? (speaking style)
- Do interruptions cluster at specific turn numbers? (conversation length issue)
- Is silence_duration_ms appropriate for the interview type? (behavioral vs technical)

## Feedback Pipeline Events

| event_type | Meaning | Key Fields |
|------------|---------|------------|
| `transcript_preprocessing_started` | Transcript cleanup phase | |
| `transcript_preprocessing_completed` | Cleanup done | `input_pairs`, `output_pairs`, `duration_seconds` |
| `question_processing_started` | Per-question analysis | `question_index` |
| `question_processing_ai_output_repaired` | AI output needed correction (WARNING) | `field`, `old_value`, `new_value` |
| `dimension_synthesis_error` | Dimension scoring failed (ERROR) | `dimension`, `error` |
| `overall_score_calculated` | Final score computed | `score` |

### Known Feedback Failure Patterns

- **`DemonstrationLevel` enum ValueError**: AI returns `"DemonstrationLevel.DOES_NOT_DEMONSTRATE"` (Python repr) instead of `"does_not_demonstrate"`. Check `dimension_synthesizer.py` for enum parsing.
- **Zero transcripts saved**: Short sessions may not accumulate transcripts. Check `transcript_save` event count = 0.
- **`overall_score = 0`**: Usually means dimension synthesis errors silently defaulted scores. Cross-reference with `dimension_synthesis_error` count.

## Session Lifecycle Reconstruction

To reconstruct a complete session lifecycle from logs:

1. **Group by trace ID** — all entries in the same trace belong to one session
2. **Order by timestamp** — reconstruct chronological flow
3. **Map phases:**
   - **Setup**: `connection_established` → `session_started` → first `turn_started`
   - **Active**: alternating `speech_started`/`speech_stopped` and `turn_started`/`turn_completed`
   - **Teardown**: `audio_stream_ended` → `transcript_save` → `interview_completed`
   - **Post-session**: `feedback_generation_started` → `feedback_generation_completed`
   - **Cleanup**: `connection_closed` (or `ping_failure_cascade` if stale)
4. **Flag gaps**: Any phase missing or >60s gap between expected consecutive events = anomaly
