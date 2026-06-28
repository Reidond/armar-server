---
name: python-best-practices
description: >
  Expert Python conventions for the modern 3.12+ era: PEP 695 generics and type
  aliases, dataclass/TypedDict/Protocol/pydantic selection, src layout, exception
  handling and chaining, structured logging, asyncio TaskGroup patterns, pytest
  fixtures and parametrization, ruff linting norms, performance idioms, and recent
  3.12/3.13/3.14 changes. Auto-loads as background knowledge when writing or
  reviewing Python code, designing Python modules, fixing Python bugs, or setting
  up Python tooling in this project.
user-invocable: false
metadata:
  type: reference
---

# Python Best Practices (3.12+ era)

## Role

Background knowledge for writing and reviewing Python in this project. Conventions
are calibrated to mid-2026: Python 3.12 is the floor, 3.14 is current. Verified
against official docs, PEPs, and production experience reports (see
`.specs/skill-python-best-practices/research-brief.md` for sources).

Package management, virtualenvs, and dependency workflows are owned by the
`uv-python-tooling` skill — uv is the project standard; do not hand-roll pip/poetry.

## When This Skill Activates

- Writing or modifying any `.py` file
- Reviewing Python code or designing Python module structure
- Configuring Python tooling (pyproject.toml, ruff, type checker, pytest)

---

## 1. Version Targeting: 3.12 Baseline, Flag Newer Features

Assume Python 3.12+ syntax everywhere. Features below are tagged `3.13+` or `3.14+`
— check the project's `requires-python` before using them. On 3.14 targets, do NOT
add `from __future__ import annotations`: PEP 649 defers annotation evaluation
natively, and the future import now diverges from default semantics.

## 2. Typing: PEP 695 Syntax, Builtin Generics, `X | None`

New code uses the 3.12 type-parameter syntax. Variance is inferred; no
TypeVar/Generic ceremony. Builtin generics, `|` unions, `None` last.

```python
# GOOD
type JsonScalar = str | int | float | bool | None

def first[T](items: Sequence[T]) -> T: ...

class Repo[M: BaseModel]:                  # bound via colon
    def get(self, id: str) -> M | None: ...

# BAD — legacy ceremony in new code
T = TypeVar("T")
JsonScalar: TypeAlias = Union[str, int, float, bool, None]

class Repo(Generic[M]):
    def get(self, id: str) -> Optional[M]: ...
```

Accept abstract types in arguments (`Iterable`, `Sequence`, `Mapping`); return
concrete types (`list`, `dict`). Avoid union returns that force `isinstance()` on
callers.

## 3. `Any` Disables Checking — Prefer `object` or Precision

`Any` propagates uncheckedness through everything it touches. For "accepts any
value but performs no operations on it", use `object`. Reserve `Any` for genuinely
inexpressible types, with a comment. Use `typing.TypeIs` (3.13+) to write narrowing
predicates instead of returning bare `bool`. TypeIs requires the narrowed type to be
assignable to the parameter type — for invariant narrowing like `list[object]` →
`list[str]`, only `TypeGuard` works.

```python
# GOOD
def log_value(value: object) -> None: ...
def is_alert(v: object) -> TypeIs[RiskAlert]: ...
def is_str_list(v: list[object]) -> TypeGuard[list[str]]: ...  # invariant: TypeIs rejected here

# BAD — silently un-types every caller
def log_value(value: Any) -> None: ...
```

## 4. Data Modeling: Pick by Trust Boundary, Not Habit

| Need | Use |
|------|-----|
| Internal domain object, trusted data | `@dataclass(slots=True)` (`frozen=True` if immutable, `kw_only=True` for 4+ fields) |
| Validating untrusted external input (API bodies, config, LLM output) | pydantic model — at the boundary only |
| Typing a dict you don't control (third-party JSON) | `TypedDict` |
| Interface a consumer must satisfy | `Protocol` (structural), not ABC inheritance |

Pydantic runs a validation pipeline on every instantiation (~5-50x dataclass cost).
Parse once at the edge, convert to plain dataclasses for the core.

```python
# GOOD — pydantic at the edge, dataclass inside
class AlertPayload(BaseModel):            # untrusted API input
    country: str
    severity: int

@dataclass(slots=True, frozen=True)
class RiskAlert:                          # trusted internal object
    country: str
    severity: Severity

# BAD — validation tax on a hot internal path
class GridCell(BaseModel):                # instantiated 1M times per request
    lat: float
    lon: float
```

## 5. TypedDict Is Static-Only — Never Trust It at Runtime

TypedDict performs zero runtime checks; a mistyped payload passes silently. Use it
to *describe* shapes, pydantic/msgspec to *enforce* them. Mark optionality with
`NotRequired`, immutability with `ReadOnly` (3.13+), and use `Literal`
discriminators so checkers narrow the whole shape from one field.

```python
# GOOD
class Success(TypedDict):
    status: Literal["success"]
    data: dict[str, object]

class Failure(TypedDict):
    status: Literal["error"]
    message: str

type ApiResponse = Success | Failure      # narrowed by checking ["status"]
```

## 6. Project Layout: src Layout, Tests Outside

Use `src/<package>/` with `tests/` at the repo root. The src layout forces imports
to resolve against the *installed* package, so packaging mistakes (module missing
from the wheel) fail in tests instead of in production. Flat layout is acceptable
only for throwaway scripts. (PyPA recommendation.)

```
pyproject.toml
src/travel_risk/...
tests/...
```

## 7. Exceptions: Catch Specific and Low, Handle Broad Only at Edges

Raise low, catch high. Inner layers raise precise exceptions and let them
propagate; only process edges (CLI main, request handler, worker loop) catch
broadly — and there they must log with traceback and apply a deliberate policy
(crash, retry, 500). Never bare `except:` (also traps `KeyboardInterrupt`).
Define one project base exception and subclass it.

```python
# GOOD
try:
    risk = fetch_country_risk(code)
except CountryNotFoundError:
    return None

# BAD — low-level broad catch hides bugs and corrupts state silently
try:
    risk = fetch_country_risk(code)
except Exception:
    risk = DEFAULT_RISK
```

## 8. Chain Exceptions with `from`; No Control Flow in `finally`

Re-raising as a domain error must preserve the cause: `raise X from err`.
`from None` only when deliberately hiding internals (e.g., secrets in tracebacks),
with a comment. `return`/`break`/`continue` inside `finally` silently swallows
in-flight exceptions — a SyntaxWarning since 3.14 (PEP 765); never do it.

```python
# GOOD
except KeyError as err:
    raise ConfigError(f"missing key: {key}") from err

# BAD — original traceback lost; debugging dead-ends here
except KeyError:
    raise ConfigError(f"missing key: {key}")
```

`TaskGroup` failures arrive as `ExceptionGroup` — handle with `except*` (3.11+):

```python
except* httpx.HTTPError as eg:
    for e in eg.exceptions: ...
```

## 9. Logging: Module Loggers, Lazy Args, Structure Over Prose

`logger = logging.getLogger(__name__)` per module. Pass interpolation args lazily —
f-strings in log calls always pay formatting cost and destabilize the message
template that aggregators group by. Use `logger.exception(...)` in except blocks.
Libraries never attach handlers; configure once at the entry point (`dictConfig`,
or structlog for services — bind request context via `structlog.contextvars`,
which is async-safe where thread-locals bleed across tasks).

```python
# GOOD
logger.info("risk computed country=%s score=%s", code, score)

# BAD — eager formatting, ungroupable message
logger.info(f"risk computed country={code} score={score}")
```

## 10. Async: TaskGroup Over gather; Never Fire-and-Forget

`asyncio.TaskGroup` (3.11+) is the default for concurrent work: on any failure it
cancels siblings and raises an `ExceptionGroup`. `gather` keeps orphan tasks
running after a failure — use it only with `return_exceptions=True` and a comment
explaining why partial completion is wanted. A bare `create_task` whose result is
never held can be garbage-collected mid-flight and its exception lost.

```python
# GOOD — structured: all-or-nothing, errors surfaced
async with asyncio.TaskGroup() as tg:
    advisories = tg.create_task(fetch_advisories(code))
    weather = tg.create_task(fetch_weather(code))
result = merge(advisories.result(), weather.result())

# BAD — sibling keeps running after failure; task may vanish silently
asyncio.create_task(fetch_weather(code))          # no reference held
results = await asyncio.gather(fetch_advisories(code), fetch_weather(code))
```

Use `asyncio.timeout(...)` (3.11+) context manager rather than `wait_for` wrapping.
Tasks needing cleanup must guard with `try/finally` — cancellation raises
`CancelledError` inside them.

## 11. Async: Never Block the Event Loop

One blocking call (sync HTTP client, `time.sleep`, heavy CPU, blocking DB driver)
stalls *every* task on the loop. Use async-native libraries; push unavoidable sync
work to `await asyncio.to_thread(fn, ...)` and CPU-bound work to a process pool or
`InterpreterPoolExecutor` (3.14+). Only make a function `async` when it actually
awaits concurrent I/O — async-washing sequential code adds complexity with zero
speedup. Debug stuck loops with `python -m asyncio pstree <PID>` (3.14+).

```python
# GOOD
data = await asyncio.to_thread(legacy_sdk.fetch, code)

# BAD — freezes the whole service for the duration
data = legacy_sdk.fetch(code)        # sync network call inside a coroutine
```

## 12. Pytest: Plain Functions, Factory Fixtures, Parametrize with ids

Plain test functions + fixtures; no test classes unless grouping is essential.
Shared fixtures in `conftest.py`. Use the builtins (`tmp_path`, `monkeypatch`,
`capsys`) over hand-rolled equivalents. When fixtures multiply into near-clones,
collapse them into one factory fixture.

```python
# GOOD — one factory, explicit variation in the test
@pytest.fixture
def make_traveler():
    def _make(**overrides) -> Traveler:
        return Traveler(**{**DEFAULTS, **overrides})
    return _make

# BAD — fixture proliferation
@pytest.fixture
def traveler_with_visa(): ...
@pytest.fixture
def traveler_with_visa_and_insurance(): ...
```

Parametrize data-driven cases and give them readable ids; build expensive resources
inside fixtures, not in the parametrize list (which runs at collection time):

```python
@pytest.mark.parametrize(
    ("code", "expected"),
    [pytest.param("UA", Severity.HIGH, id="conflict-zone"),
     pytest.param("CH", Severity.LOW, id="stable")],
)
def test_severity(code, expected): ...
```

Mock at system boundaries (transport, clock, filesystem), not internal functions —
patching internals welds tests to the implementation. Avoid `autouse` fixtures with
side effects. Assert on behavior/return values, not log text.

## 13. Lint/Format: ruff with an Explicit Curated Select

ruff is both linter and formatter (replaces flake8+isort+black). Pin an explicit
`lint.select` — never `ALL`, which silently enables new rules on every upgrade and
breaks CI. Baseline set:

```toml
[tool.ruff]
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "C4", "SIM", "RET", "S", "TC", "PTH", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]   # asserts are the point of tests
```

`B` catches mutable defaults, `UP` rewrites legacy typing, `PTH` enforces pathlib,
`TC` moves type-only imports under `TYPE_CHECKING`.

## 14. Type Checking: One Strict Checker in CI

Run exactly one type checker in CI, strict mode. As of 2026: **pyright** is the
safe default (98% spec conformance, fast); mypy lags badly (58% conformance, slow)
and is no longer the reflex answer; Astral's `ty` and Meta's Pyrefly (1.0,
May 2026) are fast Rust-based contenders worth adopting once the team accepts their
maturity. Do not mix checkers — they disagree on edge cases and produce
suppression-comment churn.

## 15. Performance Idioms

- `@dataclass(slots=True)` / `__slots__` for objects created in volume (~30-50%
  memory, faster attribute access).
- Build strings with `"".join(parts)`, never `+=` in a loop.
- Generators/`yield` for large streams; comprehensions for materialized results.
- `itertools.batched(iterable, n)` (3.12+) for chunking.
- EAFP (`try/except`) is idiomatic and a *try* block is nearly free — but a *raise*
  is not; don't drive hot loops with exceptions.
- `functools.lru_cache` only on functions of hashable, immutable args; on methods
  it pins `self` forever (memory leak) — cache at module level instead.
- Measure before optimizing: `python -X importtime`, `cProfile`, `pyinstrument`.

```python
# BAD — quadratic string building; exception-driven hot loop
s = ""
for part in parts: s += part
for k in keys:
    try: total += index[k]
    except KeyError: pass        # use index.get(k) or dict lookup with default
```

## 16. Classic Correctness Anti-Patterns (Always Flag in Review)

```python
# BAD — mutable default evaluated once, shared across all calls
def add_alert(alert, alerts: list[Alert] = []): ...
# GOOD — None sentinel; in dataclasses use field(default_factory=list)
def add_alert(alert, alerts: list[Alert] | None = None):
    alerts = alerts if alerts is not None else []
```

- Late-binding closures in loops: `for x in xs: fns.append(lambda: x)` — every
  lambda sees the last `x`; bind with `lambda x=x:` or `functools.partial`.
- `is` for value comparison (`x is "done"`) — `is` checks identity; use `==`.
  Reserve `is` for `None`/sentinels.
- Shadowing builtins (`list`, `id`, `type`) or stdlib module names as file names
  (`logging.py`, `types.py`) — breaks imports in confusing ways.
- `os.path` string manipulation in new code — use `pathlib.Path` (3.14 adds
  `Path.copy`/`Path.move`, replacing most `shutil` calls).
- Wildcard imports (`from x import *`) outside `__init__.py` re-export patterns.

## 17. Recent Changes Cheat Sheet (3.12 → 3.14)

| Version | Must-know changes |
|---------|------------------|
| 3.12 (2023) | PEP 695 generics + `type` aliases; f-strings formalized (nesting/quotes allowed); `itertools.batched`; `Path.walk` |
| 3.13 (2024) | `typing.TypeIs`; TypeVar defaults (PEP 696); `ReadOnly` TypedDict; `warnings.deprecated`; `copy.replace()`; new REPL; experimental free-threading + JIT |
| 3.14 (2025) | Deferred annotations by default (PEP 649/749) — drop `from __future__ import annotations`; t-strings `t"..."` for safe templating (PEP 750); free-threading officially supported (PEP 779); `concurrent.interpreters` + `InterpreterPoolExecutor` (PEP 734); `except A, B:` legal without parens (PEP 758 — parens still required with `as`); SyntaxWarning for `return` in `finally` (PEP 765); `compression.zstd`; `map(..., strict=True)`; asyncio debug CLI |

When reviewing, treat advice predating these as suspect — especially "add the
annotations future import", "use Optional/Union", "use gather", and "mypy is the
standard".
