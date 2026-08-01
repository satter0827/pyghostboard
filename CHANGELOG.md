# Changelog

## 0.1.0 - 2026-08-01

- Add an immutable, configurable Geister domain with validated snapshots and deterministic replay.
- Add player-specific observations that structurally omit opposing ghost kinds.
- Add async persistence ports, optimistic commits, public event projection, and private JSON Lines
  records with build provenance.
- Add transport-independent AI contracts, reproducible random and information-set MCTS policies,
  an isolated JSON Lines adapter, and bounded process I/O.
- Add Rich commands for play, replay, and rule validation.
- Add versioned JSON Schema documents, typed distributions, compatibility CI, and exact-version
  release artifacts without registry publication.

Known constraints: version 0.1.0 provides local human-versus-AI play and an in-memory store. It does
not include network play, production database adapters, accounts, or a graphical interface.
