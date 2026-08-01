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

The bundled MCTS AI runs by default in a separate process and receives only the information visible
to its player. Select the reproducible baseline with `--agent random`. Use `pyghostboard --help`
for recording, replay, and rule validation options. External AI commands are passed as repeated
arguments without a shell, for example:

```shell
pyghostboard play --ai-command python --ai-command /path/to/agent.py
```

All transports enforce the same one-match lifecycle and validate setup, player views, legal
actions, and completion. Adding a bundled AI requires a policy, a JSON Lines entry module, and one
adapter registration; wire schema version 0.1.0 remains stable.

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
include `LOG_LEVEL`, `AGENT_TIMEOUT`, `AGENT_MAX_MESSAGE_BYTES`, `AGENT_MAX_STDERR_BYTES`,
`MAX_PLIES`, `AI_ITERATIONS`, `AI_EXPLORATION_WEIGHT`, `AI_ROLLOUT_PLIES`, and
`AI_SETUP_CANDIDATE_LIMIT`. For example, `PYGHOSTBOARD_AI_ITERATIONS=2000` increases the
deterministic MCTS search budget.

## Development

```shell
git clone https://github.com/satter0827/pyghostboard.git
cd pyghostboard
uv sync --locked --group dev
uv run pytest
```

Visual Studio Code users can install the recommended workspace extensions and select `App: Play`
from **Run and Debug** to synchronize the environment and start an interactive match. See the
[Visual Studio Code workflow](CONTRIBUTING.md#visual-studio-code) for shared tasks and debugging.

See the [documentation](docs/README.md) for requirements, architecture, interfaces, quality,
delivery, and operations. [Contributing](CONTRIBUTING.md) describes the complete verification and
branch workflow.

## Release scope

Version 0.1.0 covers local human-versus-AI play, reusable domain APIs, private match recording, and
external AI processes. GUI, network matchmaking, accounts, and a production database adapter are
outside this release.

This is an unofficial implementation. It does not include commercial artwork or rulebook text.

## License

Licensed under the [MIT License](https://github.com/satter0827/pyghostboard/blob/main/LICENSE).
