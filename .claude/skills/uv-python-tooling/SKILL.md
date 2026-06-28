---
name: uv-python-tooling
description: >
  Project standard for Python tooling: uv is MANDATORY for all Python operations —
  no pip, no poetry, no pyenv, no pipx, no manual venv activation. Covers project
  init (uv init, pyproject.toml), dependency management (uv add/remove/lock/sync,
  dependency groups), running code (uv run), Python version management (uv python),
  CLI tools (uvx, uv tool), PEP 723 inline-metadata scripts, workspaces/monorepos,
  building/publishing, Docker integration, CI caching, and pip/poetry-to-uv migration.
  Auto-loads whenever running Python commands, installing packages, managing
  dependencies or virtual environments, or setting up Python projects. Keywords:
  pip install, requirements.txt, pyproject.toml, uv.lock, virtualenv, venv, pytest,
  python version, package manager.
user-invocable: false
metadata:
  type: reference
---

# uv Python Tooling Conventions

## Role

Background knowledge for all Python tooling in this project. **uv replaces pip,
pip-tools, poetry, pyenv, pipx, twine, and manual virtualenv management — entirely.**
If you are about to type `pip`, `poetry`, `pyenv`, `pipx`, `python -m venv`, or
`source .venv/bin/activate`, stop and use the uv equivalent from this document.

Written against uv 0.11.x (June 2026). uv evolves fast and is pre-1.0 — for
fast-moving flags, verify against https://docs.astral.sh/uv.

## When This Skill Activates

- Running any Python command, script, test, or REPL
- Installing, removing, or upgrading Python packages
- Creating or configuring a Python project, venv, or Python version
- Writing Dockerfiles or CI pipelines that touch Python
- Migrating code that references pip/poetry/pyenv/pipx commands

---

## 1. The Golden Rule: Everything Goes Through uv

Never invoke `python`, `pip`, or tool binaries directly from the shell. uv resolves
the right interpreter and keeps the environment in sync automatically.

```bash
# BAD                                   # GOOD
pip install requests                    uv add requests
pip uninstall requests                  uv remove requests
python script.py                        uv run script.py
python -m pytest                        uv run pytest
python -m venv .venv && source ...      (nothing — uv manages .venv itself)
pyenv install 3.13                      uv python install 3.13
pipx run ruff                           uvx ruff
poetry add httpx                        uv add httpx
```

`uv run` locks and syncs the environment before every execution — commands are
stateless and never run against a stale env. There is no activation state to manage,
which matters when each shell call starts fresh.

## 2. Project Init and Structure

```bash
uv init my-app                # application: pyproject.toml, main.py, .python-version, README
uv init --package my-app     # installable app: src/ layout, uv_build backend, [project.scripts]
uv init --lib my-lib         # library: implies --package, adds py.typed
uv init --bare               # pyproject.toml only (no README, pin file, or sources)
```

- `pyproject.toml` is the single source of truth for dependencies.
- `.venv/` and `uv.lock` are created automatically on first `uv run`/`uv sync`/`uv add`.
- Never create the venv manually. Commit `uv.lock` — never gitignore it. Keep
  `.venv/` gitignored (`uv init` writes that `.gitignore` entry for you).

## 3. Dependency Management

```bash
uv add httpx                          # add runtime dep (writes pyproject + lock + env)
uv add 'httpx>=0.27'                  # with constraint
uv add --dev pytest                   # PEP 735 [dependency-groups] dev group
uv add --group lint ruff              # custom group
uv add httpx --optional network       # extra ([project.optional-dependencies])
uv add git+https://github.com/encode/httpx --tag 0.27.0   # git source
uv add --editable ../other-pkg       # local editable path source
uv remove httpx                       # also removes now-orphaned transitive deps
uv lock --upgrade                     # upgrade everything within constraints
uv lock --upgrade-package httpx       # upgrade one package
uv tree                               # inspect resolved dependency tree
```

```bash
# BAD — bypasses pyproject.toml and uv.lock; next exact sync removes the package
uv pip install httpx

# GOOD — declarative, locked, reproducible
uv add httpx
```

Dev tooling (pytest, mypy, ruff-as-library) belongs in the `dev` group. The `dev`
group syncs by default; exclude in production with `--no-dev`.

Temporary one-off dependency without touching the project:

```bash
uv run --with rich python -c "from rich import print; print('[bold]hi')"
```

## 4. Lockfile Discipline

`uv.lock` is universal (one file covers all platforms and Python versions),
machine-generated, and **never hand-edited**.

- Local dev: `uv run` / `uv sync` auto-update the lockfile when `pyproject.toml`
  changed. New upstream releases do NOT make a lock stale — upgrades are explicit.
- `uv sync` is **exact**: it removes anything not in the lockfile. `uv run` syncs
  inexactly (installs what's missing, but leaves already-installed packages that
  aren't in the lockfile alone).
- CI / Docker: always assert freshness instead of silently re-resolving.

```bash
# BAD — a stale lockfile gets silently re-resolved at build time
uv sync

# GOOD — fail the build if pyproject.toml and uv.lock disagree
uv sync --locked
```

- `--locked`: error if the lockfile is out of date (default choice for CI/Docker).
- `--frozen`: use the lockfile as-is without even checking freshness (offline /
  later pipeline stages only).
- `uv lock --check`: freshness check without syncing.
- Lockfile merge conflict: keep one side, re-run `uv lock` — never merge by hand.
- Need a `requirements.txt` for an external tool: generate it, don't maintain it —
  `uv export --format requirements.txt -o requirements.txt`.

## 5. Running Things: uv run, Never Activate

```bash
# BAD — activation state, stale env, PATH may resolve to system python
source .venv/bin/activate && pytest

# GOOD
uv run pytest tests/
uv run python -c "import sys; print(sys.version)"
uv run python                          # REPL inside the project env
uv run --package api uvicorn app:app  # workspace member (see §9)
uv run bash scripts/release.sh        # non-Python commands get the env too
```

- `uv run --no-project` skips the project env (pure interpreter).
- In Python code, spawn subprocess interpreters with `sys.executable`, never the
  string `"python"` — and never shell out to pip (uv envs don't even contain pip);
  shell out to `uv` if env mutation is required.

## 6. Python Version Management (replaces pyenv)

```bash
uv python install 3.13         # install (auto-download is also on by default)
uv python pin 3.13             # write .python-version (commit this file)
uv python list                 # installed + available
uv python find '>=3.12'        # locate an interpreter
uv python upgrade              # transparent patch upgrades (3.13.4 → 3.13.5)
uv run --python 3.12 pytest    # one-off run on a different version
```

Two pins, different jobs: `.python-version` selects the exact interpreter uv uses;
`requires-python` in `pyproject.toml` bounds dependency resolution. Commit both and
keep them consistent. uv prefers its own managed interpreters (`python-preference: managed`, the default)
and puts them on PATH. Do not install Pythons via pyenv/brew for project use.

## 7. Tools: uvx and uv tool (replaces pipx)

```bash
uvx ruff check .                       # ephemeral, isolated run (alias: uv tool run)
uvx ruff@0.4.0 check .                 # exact version
uvx --from 'httpie' http example.com   # package name ≠ command name
uvx --with mkdocs-material mkdocs serve  # tool + plugin
uv tool install ruff                   # persistent install on PATH
uv tool upgrade --all
uv tool list / uv tool uninstall ruff
```

**Boundary rule** — tools that import your project or its deps must run in the
project env:

```bash
# BAD — isolated env cannot see the project; imports fail / Python conflicts
uvx pytest
uvx mypy src/

# GOOD — add to dev group, run in project env
uv add --dev pytest mypy
uv run pytest
uv run mypy src/
```

Use `uvx` only for standalone CLIs whose operation doesn't depend on project code.

## 8. Single-File Scripts (PEP 723)

For utilities that don't belong to the project env:

```bash
uv init --script tool.py --python 3.13
uv add --script tool.py 'requests<3' rich   # writes the inline block
uv run tool.py
uv lock --script tool.py                     # adjacent lockfile for reproducibility
```

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["requests<3", "rich"]
# ///
```

Executable shebang: `#!/usr/bin/env -S uv run --script`.

**Caveat**: a script with an inline metadata block IGNORES the surrounding project's
dependencies, even when run inside the project. Declare everything the script
imports in its own block.

## 9. Workspaces (Monorepos)

```toml
# root pyproject.toml
[tool.uv.workspace]
members = ["packages/*"]
exclude = ["packages/experimental"]

# a member depending on another member
[project]
dependencies = ["shared-models"]
[tool.uv.sources]
shared-models = { workspace = true }   # installed editable
```

- One `uv.lock` for the whole workspace; `uv lock` operates on everything.
- Target a member: `uv run --package <name> ...`, `uv sync --package <name>`,
  `uv add --package <name> <dep>`.
- One `requires-python` (intersection of all members). Members needing conflicting
  deps or Python versions should be plain path dependencies, not workspace members.

## 10. Building and Publishing (replaces build/twine)

```bash
uv version --bump minor          # bump version (also: major, patch, rc, --dry-run)
uv build                         # sdist + wheel into dist/
uv build --no-sources            # pre-publish check: build without tool.uv.sources
uv publish                       # PyPI via UV_PUBLISH_TOKEN or trusted publishing
uv run --with my-pkg --no-project -- python -c "import my_pkg"   # smoke test
```

New packages get the `uv_build` backend by default; a `[build-system]` table is
required for the project to be installed as a package.

## 11. Docker and CI (condensed)

Full Dockerfile and GitHub Actions YAML: see
[references/docker-and-ci.md](references/docker-and-ci.md). The non-negotiables:

- Get uv via `COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /bin/` — pin the tag.
- Two-layer install for caching: `uv sync --locked --no-install-project` with only
  `pyproject.toml` + `uv.lock` bind-mounted, then `COPY . .` and `uv sync --locked`.
- Cache mount: `--mount=type=cache,target=/root/.cache/uv` with `UV_LINK_MODE=copy`.
- Production images: `UV_COMPILE_BYTECODE=1`, `--no-dev`, `--no-editable`,
  multi-stage copy of `/app/.venv` only.
- Add `.venv` to `.dockerignore` — a host venv copied into an image is broken.
- CI: `astral-sh/setup-uv` pinned with `version:` and `enable-cache: true`, then
  `uv python install`, `uv sync --locked`, `uv run pytest`. Shrink persisted caches
  with `uv cache prune --ci`.

## 12. Migration Map: pip / poetry / pyenv / pipx → uv

| Legacy command | uv equivalent |
|---|---|
| `pip install X` | `uv add X` |
| `pip install -r requirements.txt` (fresh setup) | `uv sync` |
| `pip uninstall X` | `uv remove X` |
| `pip list` / `pip show X` | `uv pip list` / `uv tree` |
| `pip freeze > requirements.txt` | `uv export --format requirements.txt -o requirements.txt` |
| `pip-compile requirements.in` | `uv lock` |
| `pip-sync` | `uv sync` |
| `python -m venv .venv` | (automatic; explicit: `uv venv`) |
| `source .venv/bin/activate && CMD` | `uv run CMD` |
| `poetry init` / `poetry new` | `uv init` / `uv init --package` |
| `poetry add X` / `poetry add -G dev X` | `uv add X` / `uv add --dev X` |
| `poetry remove X` | `uv remove X` |
| `poetry install` | `uv sync` |
| `poetry lock` | `uv lock` |
| `poetry update [X]` | `uv lock --upgrade` / `uv lock --upgrade-package X` |
| `poetry run CMD` / `poetry shell` | `uv run CMD` (no shell needed) |
| `poetry build` / `poetry publish` | `uv build` / `uv publish` |
| `poetry version minor` | `uv version --bump minor` |
| `pyenv install 3.13` / `pyenv local 3.13` | `uv python install 3.13` / `uv python pin 3.13` |
| `pipx run X` / `pipx install X` | `uvx X` / `uv tool install X` |
| `pipx upgrade-all` | `uv tool upgrade --all` |
| `twine upload dist/*` | `uv publish` |

Converting an existing pip project: `uv init`, then `uv add -r requirements.txt`
(plain requirements file). With a pip-tools layout, instead use
`uv add -r requirements.in -c requirements.txt` (the `-c` constraint preserves the
compiled pins) and `uv add --dev -r requirements-dev.in -c requirements-dev.txt`.
Then delete the requirements files. Poetry projects: `uvx migrate-to-uv`.

## 13. Anti-Patterns

1. **Mixing pip into a uv env** — `pip install` / `uv pip install` in a project
   bypasses the lockfile; the next exact `uv sync` deletes the package. Use `uv add`.
2. **Activating the venv** — stale env, lost activation state between shell calls,
   PATH ambiguity. Use `uv run`.
3. **Hand-editing or gitignoring `uv.lock`** — commit it, regenerate with `uv lock`,
   resolve merge conflicts by re-locking.
4. **Bare `uv sync` in CI/Docker** — silently re-resolves a stale lock. Use
   `uv sync --locked`.
5. **`uvx pytest` / `uvx mypy`** — isolated tool env can't see the project. Use
   `uv run` after `uv add --dev`.
6. **pyenv/brew Pythons for project use** — interpreter drift. Use `uv python` +
   committed `.python-version`.
7. **`subprocess.run(["python", ...])` or shelling out to pip** — wrong interpreter
   via PATH; pip is absent from uv envs. Use `sys.executable`; mutate envs via `uv`.
8. **Shipping the host `.venv` in Docker images** — platform-specific, broken.
   `.dockerignore` it; `uv sync --locked` inside the image.
9. **Maintaining requirements.txt alongside pyproject.toml** — dual sources of truth
   drift. Generate on demand with `uv export`.
10. **Importing project deps from a PEP 723 script** — inline metadata makes uv
    ignore project dependencies. Declare them in the script block.
11. **Unpinned uv in CI/Docker** (`uv:latest`, setup-uv without `version:`) —
    pre-1.0 behavior changes break builds. Pin and upgrade deliberately — new uv
    releases also carry security-patched managed-Python builds.

## 14. Escape Hatch: the uv pip Interface

`uv pip install/compile/sync` exists for legacy interop only (e.g. a vendor doc
demands pip semantics, or you manage a non-project env). It does NOT touch
`pyproject.toml` or `uv.lock`. Differences from real pip: requires a venv by default
(`--system` to opt out), no `--user`, ignores pip config files, stricter pre-release
handling. Never use it for dependency management inside a uv project.

## Additional Resources

- Full Dockerfile and GitHub Actions patterns:
  [references/docker-and-ci.md](references/docker-and-ci.md)
- Research brief with sources: `.specs/skill-uv-python-tooling/research-brief.md`
- Official docs (verify fast-moving flags): https://docs.astral.sh/uv
