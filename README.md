# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

pyghostboard is a typed Python engine for a hidden-information board game with fair AI.

> [!IMPORTANT]
> The project is in its repository-bootstrap stage. Game rules, AI, and a command-line
> interface have not been implemented yet.

[日本語版 README](README.ja.md)

## Goals

- Keep the game engine independent from user interfaces and AI implementations.
- Give an AI only the information available to the player it represents.
- Make seeded executions reproducible for testing and evaluation.
- Ship a typed, installable Python package with no mandatory runtime dependencies.

## Non-goals for the first release

- Graphical or web interfaces
- Network play or matchmaking
- Game persistence
- Automatic publishing to PyPI

## Requirements

- Python 3.11 through 3.14
- [uv](https://docs.astral.sh/uv/) for development

## Development setup

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
```

Run the same quality checks used by CI:

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest tests/unit
uv run pytest tests/integration
uv build
uv run twine check dist/*
```

## Repository structure

```text
src/pyghostboard/  Installable package
tests/unit/        Isolated behavior tests
tests/integration/ Distribution and boundary tests
docs/              Architecture documentation
```

See [Architecture](docs/architecture.md) for the intended dependency boundaries and
[Contributing](CONTRIBUTING.md) for the development workflow.

## Status

The next development step is the typed domain model. Product behavior will be introduced through
small pull requests against `develop`; `main` remains the stable integration point.

## Security

Report vulnerabilities according to the [security policy](SECURITY.md). Do not disclose security
issues in public GitHub issues.

## License

Licensed under the [MIT License](LICENSE).
