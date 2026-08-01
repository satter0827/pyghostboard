# Contributing

Thank you for contributing to pyghostboard. Keep each change focused, testable, and consistent with
the dependency boundaries in [Architecture](docs/architecture.md).

## Setup

```shell
uv sync --locked --group dev
```

## Development workflow

1. Update `develop` and create a short-lived branch.
2. Use `feature/`, `fix/`, `docs/`, `test/`, or `chore/` followed by a concise description.
3. Implement one coherent change and its tests and documentation together.
4. Run the checks listed below.
5. Open a pull request against `develop`.

Feature pull requests are squash-merged into `develop`. Release pull requests merge `develop` into
`main` with a merge commit. Direct pushes and force-pushes to both persistent branches are disabled.

## Quality checks

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest tests/unit
uv run pytest tests/integration
uv build
uv run twine check dist/*
```

Run `uv run ruff format .` before committing when formatting changes are required.

## Tests

- Unit tests cover one behavior without subprocesses, filesystems, clocks, or external services.
- Integration tests verify boundaries such as distributions, command-line execution, and complete
  game flows.
- Time-based AI tests are not allowed in CI. Use fixed seeds and iteration counts.

Do not add placeholder tests. A test must protect a public contract, invariant, or observed failure.

## Pull requests

Use a Conventional Commit prefix in the pull-request title, such as `feat:`, `fix:`, `docs:`,
`test:`, `refactor:`, or `chore:`. Explain why the change is needed, its impact, and the checks that
were run.
