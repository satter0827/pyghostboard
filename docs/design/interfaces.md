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
- `watch` for one configured AI match from one player viewpoint;
- `arena` for a new deterministic private result directory;
- `replay` for reading a private record;
- `analyze` for descriptive table or JSON output;
- `agent check` for a complete external-AI lifecycle;
- `rules validate` for validating a TOML rule file.

`play` is human-versus-AI only and selects MCTS by default. `--agent` selects one bundled policy;
repeated `--command` arguments select one external executable argument vector. The selectors are
exclusive and external commands execute directly without shell parsing. Actions accept a displayed
number, `b2 c2`, or `b2 exit`; the CUI only matches that input against supplied legal actions.

In a color-capable TTY the CUI uses one updating view containing the board, turn, previous move,
captured pieces, and result. Non-TTY output, `NO_COLOR`, and `TERM=dumb` use append-only plain text.
`replay` accepts a player viewpoint, step mode, and an automatic-play delay.

Human-facing text uses GNU gettext. Language resolution is `--language`,
`PYGHOSTBOARD_LANGUAGE`, operating-system locale, then English. JSON keys, enum values, Schema
identifiers, error codes, and machine-readable values are never translated.

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
- `LANGUAGE` selects `en` or `ja` when no command-line language is supplied.

Settings reject unknown values and invalid limits before a match starts.

## AI protocol

`PlayerController` defines the asynchronous placement, action, completion, and cleanup lifecycle
used by `MatchRunner`. `AgentPolicy` defines synchronous AI decisions over domain values.
`InProcessAgentController` adapts a policy directly, while `SubprocessAgentController` implements
the same lifecycle through the process-isolated protocol below. Match execution therefore does not
depend on whether input comes from a person, an in-process policy, or JSON Lines.

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

The semantic lifecycle is `new -> initialized -> playing -> finished -> closed`. Initialization,
setup, and completion happen exactly once. Actions are accepted only while playing, on the assigned
player's active turn. In-process controllers, subprocess controllers, and the JSON Lines runner share the
same validation of placements, views, legal actions, and final outcomes. Python integrations
receive the transport-independent `AgentProtocolError` for contract violations.

The bundled `RandomAgent` provides a reproducible baseline. `MctsAgent` performs information-set
search with validated deterministic limits. Third-party in-process policies implement
`AgentPolicy`; third-party process agents implement the versioned JSON Lines shapes.

The setup candidate limit bounds retained placements. Small spaces are enumerated; larger spaces
are sampled reproducibly without materializing every combination. To add a bundled AI, implement
its policy and register its public name with the single bundled-agent runner.

## Public formats

Bundled JSON Schema Draft 2020-12 documents define the normative wire shapes for rules, snapshots,
events, records, AI requests, and AI responses. Each Schema has a versioned identifier and forbids
unrecognized fields. Schema generation is deterministic and CI rejects an uncommitted generated
diff.

Arena manifest, match result, and analysis documents use schema version 0.1.0. `manifest.json`
contains `running`, `completed`, or `interrupted` state and durable counters. `results.jsonl`
contains one completed or failed attempt per line. Successful `matches/NNNNNN.jsonl` files use the
existing private record format; complete state is not duplicated in another arena format.

An arena TOML document declares exactly two uniquely identified agents, a watch agent, rounds, root
seed, a complete `RuleSet`, MCTS search settings, and process and match limits. Each round schedules
two games with the agents swapped between player one and player two. An agent seed is the unsigned
64-bit prefix of SHA-256 over root seed, round, and agent identifier.

## Records and logs

A private JSON Lines record begins with a header containing its format version, distribution
version, and complete source commit. Remaining lines contain private match events. It is a secret
replay format, not a diagnostic log.

An injected `EventLogger` receives public event projections only. The default CUI logger emits
RFC 3339 UTC timestamps and WARNING-or-higher JSON to standard error. It never receives complete
snapshots, placements, private events, or record paths.
