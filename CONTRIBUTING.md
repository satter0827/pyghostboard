# Contributing

Thank you for contributing to pyghostboard. Keep each pull request focused on one cause and
consistent with the released [design](docs/design/README.md).

## Setup

```shell
uv sync --locked --group dev
```

### Visual Studio Code

Install the workspace's recommended extensions and open the repository root. Press F5 and select
`App: Play` to synchronize the locked development environment and start an interactive match in
the integrated terminal. Select `Tests: Current File` to debug the open test file.

Use **Tasks: Run Task** for the shared workflows:

- `Environment: Sync` installs the locked development dependencies.
- `Code: Format` formats Python files with Ruff.
- `Check: Fast` runs formatting, lint, type, import-boundary, structure, and unit checks.
- `Test: All` runs the complete test suite.

The workspace uses `.venv` and enables pytest discovery, Ruff formatting, and Ruff fixes for Python
files. These settings do not change non-Python files on save.

## Branches and worktrees

`develop` is the integration branch. `main` contains release-ready revisions. Both branches require
a pull request; direct pushes, force-pushes, and deletion are prohibited.

Create short-lived branches from the latest `origin/develop`. Use `feature/`, `fix/`, `refactor/`,
`test/`, `docs/`, or `chore/` followed by a concise purpose. When work proceeds in parallel, use one
Git worktree per branch and never share a worktree between tasks.

```shell
git fetch origin
git worktree add ../pyghostboard-task -b fix/task-name origin/develop
```

Keep one cause and one ownership boundary in each branch. If two changes modify the same
responsibility or files, combine them or complete them in dependency order. Before merging, bring
the latest integration state into the short-lived branch without rewriting published history.

```shell
git fetch origin
git merge --no-edit origin/develop
```

Short-lived pull requests are squash-merged into `develop`. Releases merge `develop` into `main`
with a merge commit. Pull requests to `main` from any other branch are rejected. In this
single-maintainer repository, the maintainer reviews the completed checks and performs the merge
through GitHub; automated agents do not merge pull requests to `main`. Do not merge `main` back into
`develop` after a release. Main pull-request checks validate GitHub's test merge against the current
main revision.

After main push CI succeeds, a maintainer may tag that exact commit with `vX.Y.Z`. The tag workflow
builds and verifies wheel and source archives and retains them as Actions artifacts. This repository
does not publish distributions to PyPI, TestPyPI, or another package registry.

## Verification

Run the fast checks while implementing:

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run lint-imports
uv run pytest tests/structure
uv run pytest tests/unit
```

Before opening a pull request, run the complete local checks:

```shell
uv run coverage erase
uv run coverage run -m pytest tests/unit
uv run coverage run --append -m pytest tests/integration
uv run coverage report
uv build
uv run twine check dist/*
uv audit --locked --preview-features audit-command
```

`uv audit` contacts the configured vulnerability service. A network failure is an environment
failure, not evidence that dependencies are safe.

Run `uv run python tools/generate_schemas.py` after changing a public JSON model and include the
generated schema changes in the same pull request.

## Test boundaries

- Unit tests protect one contract or invariant without network access, subprocesses, the real
  filesystem, or the real clock.
- Integration tests verify boundaries such as distributions, command-line execution, connected
  modules, and complete game flows.
- Seeded and AI behavior uses fixed seeds and iteration counts. Elapsed time is not a CI assertion.
- Every test protects a public contract, invariant, or reproduced failure. Do not add placeholders.

Add specialized categories such as benchmarks or resource-serial tests only when implemented
behavior requires them.

## Pull requests

Use a Conventional Commit prefix in the title, such as `feat:`, `fix:`, `refactor:`, `test:`,
`docs:`, or `chore:`. Describe the cause, affected requirements and design, what remains outside
the change, automated evidence, human decisions, manual procedures, and the exact validation
performed. Update the design in the same pull request when an implemented contract changes.
