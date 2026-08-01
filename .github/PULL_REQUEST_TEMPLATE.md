## Purpose

Describe the problem or decision addressed by this change.

## Cause

Identify the responsibility or boundary that owns the behavior.

## Changes

Describe the behavior, tests, configuration, and documentation changed together.

## Requirements and design

List affected `FR-###` or `QR-###` requirements and the design documents changed with them. Write
`None` when the change does not affect a released contract.

## Scope

List affected areas and anything intentionally left outside this pull request.

- [ ] Domain or game rules
- [ ] Player observation
- [ ] AI policy
- [ ] Public API or CLI
- [ ] Packaging or dependencies
- [ ] Repository or CI
- [ ] Documentation only

## Evidence

### Automated

List the exact commands or scenarios used to validate the change.

### Human decisions

Record decisions that require judgment, including the reviewer and completion evidence. Write
`None` when no human-only decision applies.

### Manual procedures

Record the owner, trigger, inputs, completion condition, and durable evidence for any manual work.
Write `None` when no manual procedure applies.

## Checklist

- [ ] The pull request has one coherent purpose.
- [ ] Tests protect the changed contract, invariant, or reproduced failure.
- [ ] Implemented contracts and their design documents change together.
- [ ] Formatting, linting, typing, and relevant tests pass.
- [ ] No secrets, generated caches, or unrelated changes are included.
