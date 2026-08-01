# Contributing

Thank you for contributing to pyghostboard. Keep each pull request focused on one cause and
consistent with the dependency boundaries in [Architecture](docs/architecture.md).

## Setup

```shell
uv sync --locked --group dev
```

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
with a merge commit. Pull requests to `main` from any other branch are rejected. A release pull
request requires approval from at least one reviewer other than its author, and a human maintainer
performs the merge. New commits dismiss an existing approval. Do not merge `main` back into
`develop` after a release; main pull-request checks validate GitHub's test merge against the current
main revision.

## Verification

Run the fast checks while implementing:

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy
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
`docs:`, or `chore:`. Describe the cause, the ownership boundary changed, what remains outside the
change, and the exact validation performed. Update architecture documentation in the same pull
request when a dependency boundary changes.
