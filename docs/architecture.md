# Architecture

## Purpose

pyghostboard separates game rules, player-visible information, decision policies, and user
interfaces. The separation prevents an AI from reading hidden state and keeps the game engine
usable outside a specific interface.

## Intended boundaries

```text
CLI ───────────────┐
                   v
Public API ──> Domain model <── Observation
                   ^                  |
                   |                  v
              Game rules        AI policies
```

- The domain model owns the complete game state and is the only layer allowed to mutate it.
- Game rules operate on domain types and do not depend on AI, CLI, storage, or network code.
- An observation contains only information visible to one player.
- AI policies receive observations and legal actions, never the complete hidden state.
- Interfaces call the public API instead of modifying domain objects directly.

## Dependency direction

The domain package may depend only on the Python standard library and other domain modules. AI and
interface packages may depend on the public domain API. Dependencies in the opposite direction are
not allowed.

## Current state

Only the installable package boundary and its distribution contract exist. Modules are added when
their behavior is implemented and tested; empty architectural placeholders are intentionally
avoided.

## Change policy

Architecture changes must update this document in the same pull request. Reusable abstractions are
introduced only after at least two concrete callers require the same behavior.
