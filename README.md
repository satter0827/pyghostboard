# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

pyghostboard is a typed Geister game domain with persistence-friendly APIs, an isolated AI
protocol, and a rich command-line interface.

[日本語版 README](README.ja.md)

## Install and play

Python 3.11 through 3.14 is supported.

```shell
pip install pyghostboard
pyghostboard play --seed 7
```

The bundled random AI runs in a separate process and receives only the information visible to its
player. Use `pyghostboard --help` for custom AI, recording, replay, and rule validation options.

## Use the domain

```python
from uuid import uuid4

from pyghostboard.domain import Match, Placement, Player, RuleSet

rules = RuleSet.standard()
one = rules.start_squares(Player.ONE)
two = rules.start_squares(Player.TWO)
match = Match.start(
    uuid4(),
    rules,
    {
        Player.ONE: Placement(good=one[:4], bad=one[4:]),
        Player.TWO: Placement(good=two[:4], bad=two[4:]),
    },
)
view = match.view_for(Player.ONE)
match = match.play(Player.ONE, view.legal_actions[0]).match
```

Trusted applications can persist `PrivateMatchSnapshot` values directly or use the async
`MatchService` and `MatchStore` port. Bundled JSON Schema documents describe every public wire
format. `RuleSet` customization is data-only: board dimensions, starting areas, exits, shared
movement vectors, piece counts, and a subset of the three built-in victory conditions.

Runtime limits are externally configurable with the `PYGHOSTBOARD_` prefix. For example,
`PYGHOSTBOARD_AGENT_TIMEOUT=5` changes the AI response deadline. Message size, retained stderr,
maximum ply count, and log level have corresponding settings in `RuntimeSettings`.

## Development

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
uv run pytest
```

See [Architecture](docs/architecture.md) for trust and dependency boundaries and
[Contributing](CONTRIBUTING.md) for the complete verification and branch workflow.

## Release scope

Version 0.1.0 covers local human-versus-AI play, reusable domain APIs, private match recording, and
external AI processes. GUI, network matchmaking, accounts, and a production database adapter are
outside this release.

This is an unofficial implementation. It does not include commercial artwork or rulebook text.

## License

Licensed under the [MIT License](LICENSE).
