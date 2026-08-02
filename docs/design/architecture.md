# Architecture

## System boundary

A trusted host owns complete match state. Human players and AI processes interact through
player-specific views. Operating-system users able to inspect or debug the trusted host remain
outside the isolation boundary.

```text
CUI ───────────────┐
External app ──────┼──> Adapters ──> Application ──> Domain
                   └──> PlayerController ──> AgentPolicy ──> PlayerView
AI process <────────── JSON Lines adapter ────────────────┘
Arena files <───────── private result adapter
```

Dependencies point inward:

- `domain` owns rules, immutable values, transitions, observations, snapshots, events, replay, and
  JSON codecs. It performs no infrastructure I/O.
- `application` coordinates loading, transitions, atomic commits, and public event projection
  through injected ports. `MatchRunner` owns the complete-match controller lifecycle.
- `agents` defines transport-independent policy and client protocols. Bundled random and MCTS
  policies depend only on public observations, public rules, and pure domain transitions.
- `protocol` defines versioned AI messages using public domain values.
- `adapters` own environment and TOML configuration, subprocess communication, and private record
  files. Adapter modules do not depend on sibling adapters.
- `cli` separates command assembly, configuration resolution, human input, gettext, and display.
  It assembles adapters and application services but does not evaluate game rules.

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

The display is a `MatchObserver` for one configured player. TTY capability selects either a Rich
Live screen or an append-only renderer without changing its input contract. Language resolution
happens before the Typer command tree is constructed, while stable wire names and error codes stay
outside gettext.

## Match execution and agent contracts

`PlayerController` is the application-owned asynchronous input lifecycle shared by people and AI.
`MatchRunner` initializes two controllers, collects placements, advances the persisted match,
emits one player-safe observer stream, forwards private events only to an explicit trusted sink,
reports the result, and closes both controllers on every exit path.

`AgentPolicy` owns synchronous AI decisions without knowledge of JSON, processes, or timeouts.
`InProcessAgentController` adapts a policy directly, while `SubprocessAgentController` translates
the same calls to versioned JSON Lines messages. One lifecycle validator enforces
`new -> initialized -> playing -> finished -> closed` across both controllers and the wire runner,
including placement, player, active-turn, legal-action, and final-outcome validation.

Each controller receives a `PlayerContext` containing its player, public rules, and seed. The bundled
MCTS policy asks the domain's live-position engine to construct hypotheses from player-safe
observations and sampled opposing piece kinds; the AI layer neither imports nor fabricates private
persistence models. Fixed iteration, rollout, and setup candidate limits make equal inputs and
configuration reproducible. New decision strategies implement `AgentPolicy`; input transports
implement `PlayerController`.

## AI experiment execution

`ArenaRunner` validates the complete `ArenaConfig`, derives per-pair agent seeds, schedules every
agent pairing with swapped sides, and runs each game through `MatchRunner`. It depends on injected
`ArenaControllerFactory` and `ArenaStore` ports and performs no file or process I/O. The CLI
constructs subprocess controllers and filesystem storage; arena rules never fork into a second
match engine.

The arena adapter exclusively locks one private directory and stores its normalized configuration,
atomic manifest, and one directory per attempt. A successful attempt atomically promotes its result
and optional private record together. An expected AI failure becomes a durable failed attempt;
unexpected host failure marks the run interrupted. Resume validates the stored plan and runs only
indexes with no durable attempt.

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
