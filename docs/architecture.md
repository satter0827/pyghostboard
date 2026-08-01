# Architecture

## Purpose

pyghostboard provides a reusable Geister domain, persistence-friendly application services, and an
isolated AI protocol. A trusted host owns complete state; players and AI processes receive only a
player-specific view.

## Dependency direction

```text
CLI ───────────────┐
External app ──────┼──> Adapters ──> Application ──> Domain
AI process <── JSON Lines protocol ────────────────> PlayerView
```

- `domain` contains immutable rules, state transitions, observations, events, snapshots, and JSON
  codecs. It never reads files, environment variables, clocks, loggers, or processes.
- `application` coordinates load, transition, atomic commit, public event projection, and an
  injected logging port through `MatchStore`.
- `adapters` own configuration, versioned recording, and subprocess I/O. The CLI configures the
  default structlog renderer and injects its logger into the application service.
- `cli` renders application results and never evaluates game rules.
- `protocol` defines versioned messages and depends only on public domain values.

Import Linter enforces these directions. Internal modules import definitions directly rather than
the package-root convenience facade. Executable repository-level constraints also live in
`tests/structure`; review-only constraints for coding agents are recorded in the root `AGENTS.md`.

## Information boundary

`PrivateMatchSnapshot` and `PrivateMatchEvent` are trusted-host values and may contain both
placements. `PlayerView` has separate shapes for owned and opposing pieces: opposing pieces do not
have a ghost-kind field. The AI subprocess receives serialized `PlayerView` values and legal
actions only. It never receives a `Match`, private snapshot, private event, or record path.

Removed pieces retain a private removal reason and square. This distinguishes capture from escape
and lets restore validation prove that an escaped good ghost left through a configured exit.

Process isolation prevents Python object access. It does not attempt to defend against an operating
system user attaching a debugger to another process.

## State and persistence

`Match.play()` is a pure transition that returns a new match and events. `Match.snapshot()` creates
a versioned persistence value; `Match.restore()` validates it before constructing a trusted match.
`MatchStore.commit()` atomically checks the previous revision, writes the new snapshot, and appends
events. Storage implementations remain outside the domain.

Private JSON Lines records begin with a `record_header` containing the record format version,
distribution version, and complete main commit SHA. Subsequent lines are private match events. The
temporary file has mode `0600` and is created beside an explicit destination so final promotion is
an atomic same-filesystem replacement.

Public JSON formats use UTF-8, Semantic Versioning, and bundled JSON Schema Draft 2020-12 schemas.
Domain events contain no timestamps so seeded executions remain reproducible.
Diagnostic logs use RFC 3339 UTC timestamps, but only public event projections are logged; complete
snapshots and placements are never passed to a logger.

## Change policy

Architecture changes update this document with their implementation. New abstractions require a
concrete boundary or at least two callers. Rule customization must preserve the property that legal
actions do not depend on an opponent's hidden ghost kinds.
