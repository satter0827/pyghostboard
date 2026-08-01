# AI protocol

Python integrations implement the transport-independent `AgentPolicy` protocol. It defines setup,
action, and completion methods using domain values. `InProcessAgentClient` executes a policy
directly. The JSON Lines protocol below is the process-isolated transport and does not define how a
policy makes decisions.

An AI is an executable that reads one UTF-8 JSON object per line from standard input and writes
one response object per line to standard output. The host launches the argument vector directly;
no shell parses it. Version 0.1.0 uses this sequence:

1. `initialize` provides the player, deterministic seed, and public rules; reply with `ready`.
2. `setup_request` asks for that player's secret placement; reply with `setup`.
3. Each `action_request` provides a `PlayerView`; reply with one listed action.
4. `finished` provides the final `PlayerView`, including the outcome; reply with `ready`.

Every response repeats the request UUID. Unknown fields, wrong versions, malformed JSON, mismatched
UUIDs, and actions outside the supplied legal-action list are rejected. The bundled schemas
`agent-request-0.1.0.schema.json` and `agent-response-0.1.0.schema.json` are the normative wire
shapes.

The host exposes owned ghost kinds but represents opponents only as occupied squares. It never
sends a private snapshot, private event, record path, or opponent placement. This object boundary
is reinforced by a separate process. It does not defend against an operating-system user with
debugger privileges.

Defaults are a 10-second response deadline, 1 MiB per message, 64 KiB retained standard error, and
1,000 plies. Standard error is drained concurrently and never parsed as protocol data. On timeout,
oversize output, invalid output, or shutdown, the POSIX process group is terminated so descendants
do not remain running. Configuration is injected through `RuntimeSettings` or `PYGHOSTBOARD_`
environment variables.

The bundled policies are `RandomAgent` and `MctsAgent`. MCTS settings use
`PYGHOSTBOARD_AI_ITERATIONS`, `PYGHOSTBOARD_AI_EXPLORATION_WEIGHT`,
`PYGHOSTBOARD_AI_ROLLOUT_PLIES`, and `PYGHOSTBOARD_AI_SETUP_CANDIDATE_LIMIT`.
