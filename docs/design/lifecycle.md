# Lifecycle

## Execution classes

- **Automated** activities are repeatable checks or transformations enforced by code, tests,
  configuration, or CI.
- **Human decision** activities require judgment about intent, usability, risk, or release
  authority.
- **Manual procedure** activities are repeatable but not automated. Their owner records the
  trigger, inputs, completion condition, and durable evidence.

Passing automation never substitutes for a required human decision or manual procedure.

## Activity controls

| Activity | Source of truth | Execution | Completion evidence |
| --- | --- | --- | --- |
| Define product behavior | [Requirements](requirements.md) | Human decision | Reviewed requirement change in the implementing pull request |
| Define rules and invariants | [Domain](domain.md), domain models | Automated and human decision | Domain tests plus design review |
| Preserve dependency direction | [Architecture](architecture.md), Import Linter configuration | Automated | `lint-imports` and structure-test results |
| Change a public JSON format | Versioned models and generated Schemas | Automated and human decision | Schema diff, conformance tests, and compatibility review |
| Verify a change | [Quality](quality.md), test and tool configuration | Automated | Required CI checks on the pull request |
| Approve API names and messages | Public facade and user-facing behavior | Human decision | Pull-request review record |
| Integrate into `develop` | Branch rules and [delivery design](delivery.md) | Automated and human decision | Required checks and squash-merge commit |
| Promote `develop` to `main` | Main ruleset and release pull request | Human decision | GitHub merge commit after required checks |
| Produce a versioned release | Tag workflow and release verifier | Manual procedure and automated | Tag on current main, successful workflow, retained artifact |
| Operate an external store | `MatchStore` contract | Manual procedure | Adapter-specific atomicity test and deployment review |
| Protect private records | [Operations](operations.md), destination policy | Manual procedure | Verified permissions and retained access record |
| Assess a vulnerability | [Security policy](../../SECURITY.md) | Human decision | Private report, impact decision, remediation record |
| Deprecate or retire a version | Changelog and security support statement | Human decision and manual procedure | Release notice, updated support policy, approved artifact action |

## Requirement evidence

| Requirements | Primary automated evidence | Required human or manual evidence |
| --- | --- | --- |
| FR-001, FR-002 | Domain and validation unit tests; complete-match integration test | Review of rule wording and supported customization |
| FR-003, QR-001 | Observation property tests; AI Schema structure tests; logging projection tests | Review of new output fields and debugger threat boundary |
| FR-004, QR-003 | Replay, restore, codec, and fixed-seed tests | Review of any new nondeterministic input |
| FR-005, QR-004 | Application-service and in-memory atomicity tests | Atomic transaction evidence for each external store |
| FR-006, QR-005 | Policy, MCTS, AI lifecycle, timeout, size, stderr, exit, and process-group tests | Review of configured production limits |
| FR-007 | CLI unit and integration tests; installed-wheel smoke tests | Usability review of prompts, names, and errors |
| FR-008 | Recorder promotion, overwrite, discard, and replay tests | Destination permission and retention review |
| FR-009, QR-007 | Schema generation and conformance; distribution and release-verifier tests | Compatibility decision for each format-version change |
| QR-002 | Import Linter and architecture structure tests | Review of new package boundaries |
| QR-006 | Main compatibility matrix | Decision to add or remove a supported platform or Python version |
| QR-008 | Required pull-request checks | Review that evidence covers the changed requirement |
