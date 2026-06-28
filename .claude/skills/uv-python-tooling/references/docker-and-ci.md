# uv in Docker and CI — Full Patterns

Companion to the `uv-python-tooling` skill, section 11. Source: official Astral
guides (docs.astral.sh/uv/guides/integration/docker/ and .../github/), fetched
June 2026 against uv 0.11.x. Pin versions; check the guides for flag changes.

## 1. Getting uv into an Image

Preferred — copy the static binaries from the distroless image (pin the tag, or a
SHA256 digest for full reproducibility):

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /bin/
```

Astral also publishes derived images with uv pre-installed
(`ghcr.io/astral-sh/uv:python3.13-trixie-slim`, Alpine/Debian variants, Python
3.9–3.14). Never use `:latest` in anything that ships.

## 2. Production Dockerfile (multi-stage, layer-cached)

```dockerfile
# ---------- builder ----------
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Layer 1: dependencies only — invalidated only when the lock or manifest changes
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable --no-dev

# Layer 2: the project itself
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# ---------- runtime ----------
FROM python:3.13-slim
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "my_app"]
```

Why each piece matters:

| Element | Purpose |
|---|---|
| `--locked` | Fail the build if `uv.lock` is stale instead of silently re-resolving |
| `--no-install-project` (layer 1) | Dependency layer survives source-code changes |
| `--no-editable` | Project installed by copy, so `.venv` is self-contained for the runtime stage |
| `--no-dev` | Exclude the dev dependency group from production |
| `UV_COMPILE_BYTECODE=1` | Pre-compile .pyc for faster container startup |
| `UV_LINK_MODE=copy` | Required when the cache mount is on a different filesystem (silences hardlink warnings) |
| `UV_PYTHON_DOWNLOADS=0` | Use the image's Python; don't fetch a managed interpreter |
| `--mount=type=cache,target=/root/.cache/uv` | BuildKit cache for wheels across builds |

Simple (non-multi-stage) variant: same two-layer `uv sync` structure, then either
`ENV PATH="/app/.venv/bin:$PATH"` or `CMD ["uv", "run", "my-app"]`.

## 3. .dockerignore — Mandatory Entry

```
.venv
```

A host `.venv` copied into an image is platform-specific and broken. Always
recreate the environment inside the image with `uv sync --locked`.

## 4. Development Containers

```bash
# bind-mount the source, but shadow .venv with an anonymous volume
docker run --rm -v .:/app -v /app/.venv my-image
```

```yaml
# docker-compose: live sync with rebuild on manifest change
services:
  app:
    build: .
    develop:
      watch:
        - action: sync
          path: .
          target: /app
          ignore: [.venv/]
        - action: rebuild
          path: ./pyproject.toml
```

## 5. GitHub Actions

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Install uv
        uses: astral-sh/setup-uv@v8          # pin to a commit SHA in real workflows
        with:
          version: "0.11.20"                  # pin uv itself
          enable-cache: true                  # built-in cache keyed on uv.lock

      - name: Set up Python
        run: uv python install                # respects .python-version

      - name: Install the project
        run: uv sync --locked --all-extras --dev

      - name: Run tests
        run: uv run pytest tests
```

Matrix testing across Python versions:

```yaml
strategy:
  matrix:
    python-version: ["3.12", "3.13", "3.14"]
steps:
  - uses: astral-sh/setup-uv@v8
    with:
      version: "0.11.20"
      python-version: ${{ matrix.python-version }}   # or env: UV_PYTHON
```

## 6. Manual Cache Management (non-GitHub CI, or fine control)

```yaml
env:
  UV_CACHE_DIR: /tmp/.uv-cache

steps:
  - uses: actions/cache@v5
    with:
      path: /tmp/.uv-cache
      key: uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
      restore-keys: |
        uv-${{ runner.os }}

  # ... uv sync --locked, uv run pytest ...

  - name: Minimize uv cache
    run: uv cache prune --ci    # drops pre-built wheels, keeps source-built ones
```

Key the cache on `uv.lock`. Run `uv cache prune --ci` before the cache is saved —
it removes artifacts that are cheap to re-download but expensive to store.

## 7. CI Lockfile Gate

Add an explicit freshness check so a forgotten `uv lock` fails fast with a clear
message (rather than failing inside `uv sync --locked`):

```yaml
- name: Verify lockfile is up to date
  run: uv lock --check
```
