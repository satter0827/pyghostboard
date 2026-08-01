# pyghostboard

[![CI](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml/badge.svg)](https://github.com/satter0827/pyghostboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/satter0827/pyghostboard/blob/main/LICENSE)

pyghostboard is a typed Geister game domain with persistence-friendly APIs, an isolated AI
protocol, and a rich command-line interface.

[日本語版 README](https://github.com/satter0827/pyghostboard/blob/main/README.ja.md)

## Install and play

Python 3.11 through 3.14 is supported. The domain API is portable Python. The CUI, isolated AI
process, and private recorder require macOS or Linux because their cleanup and file-promotion
guarantees use POSIX behavior.

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
python -m pip install .
pyghostboard play --seed 7
```

The project prepares standard wheel and source archives but does not publish them to a package
registry. A `vX.Y.Z` tag on the current `main` commit builds an exact-version artifact in GitHub
Actions.

The bundled random AI runs in a separate process and receives only the information visible to its
player. Use `pyghostboard --help` for recording, replay, and rule validation options. External AI
commands are passed as repeated arguments without a shell, for example:

```shell
pyghostboard play --ai python --ai /path/to/agent.py
```

Private records contain both players' ghost kinds and placements. Protect them as secrets. Existing
record destinations are not replaced unless `--overwrite-record` is explicitly supplied.

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

Runtime limits are externally configurable with the `PYGHOSTBOARD_` prefix. The available names
are `LOG_LEVEL`, `AGENT_TIMEOUT`, `AGENT_MAX_MESSAGE_BYTES`, `AGENT_MAX_STDERR_BYTES`, and
`MAX_PLIES`. For example, `PYGHOSTBOARD_AGENT_TIMEOUT=5` changes the AI response deadline.

## Development

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
uv run pytest
```

See [Architecture](https://github.com/satter0827/pyghostboard/blob/main/docs/architecture.md),
[AI protocol](https://github.com/satter0827/pyghostboard/blob/main/docs/ai-protocol.md), and
[integration guide](https://github.com/satter0827/pyghostboard/blob/main/docs/integration.md).
[Contributing](https://github.com/satter0827/pyghostboard/blob/main/CONTRIBUTING.md) describes the
complete verification and branch workflow.

## Release scope

Version 0.1.0 covers local human-versus-AI play, reusable domain APIs, private match recording, and
external AI processes. GUI, network matchmaking, accounts, and a production database adapter are
outside this release.

This is an unofficial implementation. It does not include commercial artwork or rulebook text.

## License

Licensed under the [MIT License](https://github.com/satter0827/pyghostboard/blob/main/LICENSE).
