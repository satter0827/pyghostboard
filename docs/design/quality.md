# Quality

## Verification model

Tests protect contracts, invariants, reproduced failures, or repository policies. The project does
not add placeholder tests or abstractions without implemented behavior.

- Unit tests isolate one behavior without network access, subprocesses, the real filesystem, or
  the real clock.
- Integration tests cover distributions, the CUI, subprocess AI, filesystem recording, connected
  application flows, and complete matches.
- Structure tests enforce dependency direction, facade use, forbidden domain I/O, public/private
  Schema separation, pinned workflow actions, shell-free subprocesses, release policy, and
  documentation organization.
- Property-based tests exercise observation noninterference and validation across generated domain
  values.
- Agent tests exercise policy lifecycle, legal-action enforcement, reproducibility, bounded MCTS
  search, and equivalence between in-process and subprocess transports.

Branch coverage must remain at least 90%. Fixed seeds and iteration counts replace elapsed-time
assertions for deterministic and AI behavior.

## Static quality controls

Ruff enforces formatting and selected correctness rules. Mypy checks source and tests in strict
mode. Import Linter enforces the declared layer contract. Public facades use explicit `__all__`
lists, and the distribution exposes `py.typed`.

`tools/i18n.py check` extracts every CLI `tr()` message, compares the deterministic POT and Japanese
PO inventories, rejects empty translations, and verifies the compiled GNU MO bytes. Distribution
verification requires POT, PO, and MO files, and the isolated-wheel smoke test runs Japanese help.

## Information security

Player-safe output is verified as a noninterference property: changing every possible opposing
ghost-kind assignment while preserving visible board state does not change the observation or
legal actions. Structure tests also prevent private model names from entering AI Schemas. MCTS
constructs hypotheses from the public view and sampled piece kinds rather than reading a trusted
snapshot.

Private records deliberately contain both placements and all ghost kinds. They use mode `0600`
temporary files beside the destination, promote atomically after successful completion, and refuse
replacement unless overwrite is explicit. The operating-system user, debugger, destination
directory permissions, and external persistence implementation remain outside repository-enforced
confidentiality guarantees.

## Integrity and failure handling

Strict model validation rejects corrupt snapshots, contradictory events, illegal actions, and
unsupported formats. Persistence conflicts and invalid commit batches do not partially update the
in-memory reference adapter; external stores must provide the same atomic guarantee.

AI input is bounded by time and size. Standard error is drained with bounded retention, abnormal
exit is reported, and descendants are terminated with the process group. The maximum-ply limit
prevents an unbounded match.

## Compatibility

Main release validation covers Python 3.11, 3.12, 3.13, and 3.14 on Ubuntu, Python 3.13 on macOS,
and the portable domain subset on Windows. Each job builds and installs the wheel before smoke
testing public imports and supported commands.

Public names, error wording, external-store atomicity, deployed branch protection, and release
approval require human review because repository tests cannot establish usability or external
configuration.

Arena tests verify multi-agent pairing, side swapping, SHA-256 seed derivation, complete and failed
subprocess games, attempt-directory promotion, reconstructable manifest state, exclusive locking,
interruption and resume, private modes, non-overwrite behavior, all four arena Schemas,
language-independent JSON, and installed command help. Analysis assertions cover agent, side,
pairing, paired-round, reason, failure, and ply descriptions only; no ranking, significance test, or
confidence claim is implemented.

The analytical scope and finding format are defined in [`scripts/review_gate.md`](../../scripts/review_gate.md).
Codex performs the initial analysis, and a human resolves its findings and decides whether to
merge. This Review Gate complements the deterministic Release Gate instead of duplicating it.

## Acceptance

A change is acceptable when its relevant requirements have automated evidence, all required CI
checks pass, generated artifacts are current, and the pull request records every human decision or
manual procedure that affected the result.
