# Architecture

## System boundary

A trusted host owns complete match state. Human players and AI processes interact through
player-specific views. Operating-system users able to inspect or debug the trusted host remain
outside the isolation boundary.

```text
CUI ───────────────┐
External app ──────┼──> Adapters ──> Application ──> Domain
                   └──> AgentClient ──> AgentPolicy ──> PlayerView
AI process <────────── JSON Lines adapter ────────────────┘
```

Dependencies point inward:

- `domain` owns rules, immutable values, transitions, observations, snapshots, events, replay, and
  JSON codecs. It performs no infrastructure I/O.
- `application` coordinates loading, transitions, atomic commits, and public event projection
  through injected `MatchStore` and `EventLogger` protocols.
- `agents` defines transport-independent policy and client protocols. Bundled random and MCTS
  policies depend only on public observations, public rules, and pure domain transitions.
- `protocol` defines versioned AI messages using public domain values.
- `adapters` own environment and TOML configuration, subprocess communication, and private record
  files. Adapter modules do not depend on sibling adapters.
- `cli` assembles adapters and application services, prompts users, and renders results. It does
  not evaluate game rules.

Internal modules import the module that defines a value. Package facade modules provide stable
imports only to external consumers. Import Linter and structure tests enforce the acyclic inward
dependency graph.

## Information flow

Private snapshots and events remain inside the trusted host, persistence adapter, or explicitly
requested private recorder. The application projects a private action event into public events
before logging or display. The AI adapter serializes only a `PlayerView`, legal actions, public
rules, request identity, and lifecycle state.

The separation is structural rather than a convention: opposing live pieces in `PlayerView` have
no kind field, and private host models cannot appear in generated AI wire Schemas.

## Agent contracts

`AgentPolicy` owns synchronous placement, action, and completion decisions without knowledge of
JSON, processes, or timeouts. `AgentClient` exposes the semantic lifecycle asynchronously to the
trusted host. `InProcessAgentClient` runs a policy directly, while `SubprocessAgent` translates the
same calls to versioned JSON Lines messages. The shared runner validates the wire lifecycle before
delegating to a policy.

Each policy receives an `AgentContext` containing its player, public rules, and seed. The bundled
MCTS policy creates hypothetical snapshots only from player-safe observations and sampled opposing
piece kinds. Fixed iteration and rollout limits make equal inputs and configuration reproducible.
New decision strategies implement `AgentPolicy`; new transports implement `AgentClient`.

## Persistence

`MatchStore.load()` returns a private snapshot or no match. `MatchStore.commit()` receives the next
snapshot, the exact event batch, and the revision observed by the caller. Creation expects revision
`-1`; later commits expect the loaded revision.

An implementation must compare the revision, replace the snapshot, and append the event batch in
one atomic transaction. A conflict or invalid batch leaves all stored values unchanged. Database
libraries remain in adapters, and restored records pass through domain validation before use.

## Platform boundary

Domain and application behavior uses portable Python. The CUI, subprocess adapter, and private
recorder require POSIX guarantees for process-group cleanup, file modes, and atomic file promotion.
Those infrastructure entry points reject Windows before performing partial work.

## Change boundary

An architecture change updates the implementation, executable dependency checks, affected public
Schemas, and these design documents in one pull request. A shared abstraction requires a concrete
boundary or at least two callers.
