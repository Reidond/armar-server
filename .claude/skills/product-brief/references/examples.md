# Product Brief — Calibration Examples

## Task Description Tone

### GOOD (spartan)

```markdown
## Problem

Users who end interviews under 5 minutes consume feedback generation tokens
for transcripts too short to produce meaningful results. No exit flow exists —
the interview just stops.

## Behavior

### When the user ends an interview before 5 minutes:

1. User clicks "Stop ExampleEntity."
2. Modal appears with two paths.
3. **"Start Over"** — interview gets status `DISCARDED`. User returns to
   creation with same settings pre-filled.
4. **"End ExampleEntity"** — reason chips appear. ExampleEntity gets `DISCARDED`.
```

Why it works: States facts. No motivation padding. Direct address ("Modal appears",
not "A modal should be displayed"). Numbers for sequences, bullets for rules.

### BAD (fluffy)

```markdown
## Problem

We believe that providing feedback for very short interviews may not deliver
sufficient value to justify the associated computational costs. Currently, when
a user decides to end their interview session prematurely, the system does not
provide any meaningful guidance or alternative options, which can lead to a
suboptimal user experience.

## Proposed Behavior

### Short ExampleEntity Scenario

When a user attempts to end an interview that has been running for less than
five minutes, we would like to present them with a helpful modal dialog that
explains the situation and offers them some choices about how they would like
to proceed going forward.
```

Why it fails: "We believe", "may not deliver sufficient value", "suboptimal user
experience" — empty calories. "We would like to present" — who cares what we'd like?
State what happens.

---

## UX Content

### GOOD (modal copy)

```
Header: "Your interview is too short for feedback"

Body: It takes at least 5 minutes of conversation to generate meaningful
feedback. Want to give it another shot? Your settings are saved.
```

Why it works: Honest about the constraint. Frames restart as the easy path.
No apology, no corporate-speak. "Your settings are saved" reduces anxiety.

### BAD (modal copy)

```
Header: "Oops! It looks like your session was a bit short"

Body: We're sorry, but unfortunately we are unable to generate feedback
for interview sessions that are shorter than 5 minutes in duration. We
apologize for any inconvenience this may cause. Please consider starting
a new interview session to get the most out of our platform.
```

Why it fails: "Oops!" is patronizing. "Unfortunately we are unable" is passive
corporate deflection. "We apologize for any inconvenience" is a non-apology
that signals the opposite of empathy. "Get the most out of our platform" is
marketing filler in a frustration context.

### GOOD (reason chips)

| Chip | Why it works |
|------|-------------|
| Just practicing | Neutral, no judgment. Validates exploration. |
| Technical issue | Actionable for the team. Clear category. |
| Wrong settings | Points to a specific UX gap upstream. |
| Not ready yet | Acknowledges emotion without labeling it. |

### BAD (reason chips)

| Chip | Why it fails |
|------|-------------|
| The interview was too hard | Leading — presumes a problem the user may not have. |
| I didn't like the questions | Invites complaint without actionable signal. |
| Other (please specify) | Free text at a frustration point = noise. |
| I'll come back later | Wishful thinking, not a reason. |

---

## Button Labels

### GOOD

| Label | Why |
|-------|-----|
| Start Over | Verb-first, 2 words, clear action. |
| End ExampleEntity | Verb-first, 2 words, honest about finality. |
| Generate Feedback | Verb-first, describes the outcome. |

### BAD

| Label | Why |
|-------|-----|
| OK | Meaningless — OK to what? |
| Click here to restart | "Click here" is redundant on a button. |
| I'd like to end my session | First person on a button is awkward. |
| Continue | Ambiguous — continue the interview or continue to end it? |
