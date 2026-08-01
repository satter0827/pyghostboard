# Repository constraints for coding agents

Read the [design index](docs/design/README.md) and the affected design documents before changing
behavior, package boundaries, public formats, delivery controls, or operating procedures.

Change an implemented contract together with its tests and design. Regenerate bundled JSON
Schemas when a public JSON model changes. Update structure tests when an executable architecture or
repository constraint changes. Record human decisions and manual procedures in the pull request;
do not describe them as automated evidence.

Run the focused checks while implementing:

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run lint-imports
uv run pytest tests/structure
uv run pytest tests/unit
```

Follow [Contributing](CONTRIBUTING.md) for branch, complete verification, and release procedures.
Unresolved alternatives belong in [notes](docs/notes/README.md), not in the released design.

## Review constraints

Follow [`scripts/review_gate.md`](scripts/review_gate.md) for constraints that require analysis or
human judgment. Do not claim that repository tests prove those constraints. Codex performs the
initial review, and a human resolves the findings and decides whether to merge.
