# Requirements

## Product purpose

pyghostboard provides a reusable, typed Geister engine and a local command-line application. It
lets a trusted host run deterministic matches against an isolated AI without revealing information
that the represented player cannot observe.

The primary users are Python developers embedding the domain or application service, AI authors
integrating an external process, and local players using the CUI.

## Functional requirements

- **FR-001 — Standard match:** The system runs a complete standard Geister match, including secret
  placement, alternating legal actions, capture, escape, and all three standard victory reasons.
- **FR-002 — Configurable rules:** The host loads validated data-only rules for board dimensions,
  starting areas, exits, piece counts, shared movement vectors, and enabled built-in victory
  conditions.
- **FR-003 — Player-safe observation:** Each player and AI receives its own ghost kinds, opposing
  occupied squares, captured information, legal actions, turn information, and outcome without
  receiving live opposing ghost kinds.
- **FR-004 — Deterministic execution:** A fixed rule set, placements, action sequence, seed, and AI
  iteration policy produce reproducible domain events and outcomes.
- **FR-005 — Application integration:** A host creates, loads, observes, and advances transitions
  through an application service, or runs a complete match through two injected player controllers,
  backed by an injected persistence port.
- **FR-006 — Replaceable AI:** The host runs a transport-independent policy in process or through a
  shell-free versioned JSON Lines subprocess, and rejects invalid lifecycle transitions,
  placements, player views, responses, actions, and final observations. The package provides
  reproducible random and information-set MCTS policies.
- **FR-007 — Local CUI:** A user can play a match, replay a private record, and validate a rule file
  through the installed `pyghostboard` command.
- **FR-008 — Private recording:** A completed local match can produce a versioned replay record with
  distribution and source provenance without silently replacing an existing destination.
- **FR-009 — Public formats:** Consumers can validate rules, snapshots, events, records, and AI
  messages against bundled versioned JSON Schemas.

## Quality requirements

- **QR-001 — Hidden-information safety:** Public observations, AI messages, and diagnostic logs do
  not expose live opposing ghost kinds, private snapshots, private events, placements, or record
  paths.
- **QR-002 — Domain isolation:** Domain code performs no file, environment, process, clock,
  configuration, or logging I/O and depends on no outer project layer.
- **QR-003 — State integrity:** Models reject unknown fields and invalid combinations; restoration
  and replay validate persisted state before it becomes trusted state.
- **QR-004 — Atomic persistence:** A persistence adapter compares the expected revision, replaces
  the snapshot, and appends its event batch as one transaction.
- **QR-005 — Bounded AI execution:** AI response time, message size, retained standard error,
  search iterations, rollout depth, setup candidates, and maximum match plies have validated
  configurable limits; subprocess cleanup includes descendants.
- **QR-006 — Compatibility:** Python 3.11 through 3.14 support the domain and application APIs on
  Windows, macOS, and Linux. The CUI, subprocess AI, and private recorder support macOS and Linux.
- **QR-007 — Typed distribution:** Wheel distributions expose explicit typed facades, bundled
  Schemas, a console entry point, an exact version, and complete source-commit provenance.
- **QR-008 — Verifiable change:** Formatting, linting, strict typing, dependency direction, tests,
  Schema generation, packaging, compatibility, and dependency auditing gate integration.

## Release scope

The 0.1 series supports local human-versus-AI play, reusable domain, application, and agent APIs,
bundled random and information-set MCTS policies, an in-memory store, private recording, replay,
configurable rules, and external AI processes.

The series does not provide a GUI, network play, matchmaking, accounts, a production database
adapter, or publication to a package registry.
