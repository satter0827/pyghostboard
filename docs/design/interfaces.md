# Interfaces

## Python API

External consumers import domain values from `pyghostboard.domain` and application services from
`pyghostboard.application`. AI integrations import policy and client contracts from
`pyghostboard.agents`. Public facade exports are explicit, unique, and resolvable. Internal modules
do not import through those convenience facades.

`RuleSet`, snapshots, events, protocol messages, and views are strict immutable models. JSON codecs
use UTF-8 and reject unknown fields or unsupported format versions.

## Command-line interface

The installed `pyghostboard` command provides:

- `play` for a local human-versus-AI match;
- `replay` for reading a private record;
- `rules validate` for validating a TOML rule file.

The CUI renders application results and reports typed failures without applying domain rules
itself. External AI commands are repeated arguments and are executed directly without shell
parsing.

## Configuration

TOML rule files contain a `rules` table matching the `RuleSet` Schema. The bundled
[`examples/rules.toml`](../../examples/rules.toml) is a complete standard configuration.

Runtime settings use the `PYGHOSTBOARD_` environment prefix:

- `LOG_LEVEL` defaults to `WARNING`;
- `AGENT_TIMEOUT` defaults to 10 seconds;
- `AGENT_MAX_MESSAGE_BYTES` defaults to 1 MiB;
- `AGENT_MAX_STDERR_BYTES` defaults to 64 KiB;
- `AI_ITERATIONS` defaults to 256;
- `AI_EXPLORATION_WEIGHT` defaults to the square root of two;
- `AI_ROLLOUT_PLIES` defaults to 96;
- `AI_SETUP_CANDIDATE_LIMIT` defaults to 256;
- `MAX_PLIES` defaults to 1,000.

Settings reject unknown values and invalid limits before a match starts.

## AI protocol

`AgentPolicy` defines synchronous setup, action, and completion methods over domain values.
`InProcessAgentClient` executes a policy directly. `SubprocessAgent` implements the same
asynchronous `AgentClient` lifecycle through the process-isolated protocol below. Gameplay code
therefore does not depend on transport details.

An AI reads one UTF-8 JSON object per line from standard input and writes one response object per
line to standard output. Protocol 0.1.0 follows this sequence:

1. `initialize` supplies the player, deterministic seed, and public rules; the AI replies `ready`.
2. `setup_request` requests that player's secret placement; the AI replies `setup`.
3. Each `action_request` supplies a `PlayerView`; the AI replies with one listed action.
4. `finished` supplies the final `PlayerView`; the AI replies `ready`.

Every response repeats the request UUID. The host rejects unknown fields, unsupported versions,
malformed JSON, mismatched UUIDs, invalid lifecycle order, and actions outside the supplied legal
list. Standard error is drained concurrently but never parsed as protocol data. Failure, timeout,
oversize output, or shutdown terminates the POSIX process group.

The bundled `RandomAgent` provides a reproducible baseline. `MctsAgent` performs information-set
search with validated deterministic limits. Third-party in-process policies implement
`AgentPolicy`; third-party process agents implement the versioned JSON Lines shapes.

## Public formats

Bundled JSON Schema Draft 2020-12 documents define the normative wire shapes for rules, snapshots,
events, records, AI requests, and AI responses. Each Schema has a versioned identifier and forbids
unrecognized fields. Schema generation is deterministic and CI rejects an uncommitted generated
diff.

## Records and logs

A private JSON Lines record begins with a header containing its format version, distribution
version, and complete source commit. Remaining lines contain private match events. It is a secret
replay format, not a diagnostic log.

An injected `EventLogger` receives public event projections only. The default CUI logger emits
RFC 3339 UTC timestamps and WARNING-or-higher JSON to standard error. It never receives complete
snapshots, placements, private events, or record paths.
