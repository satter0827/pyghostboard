# Repository constraints for coding agents

Read `docs/architecture.md` before changing package boundaries or public formats. Preserve the
following constraints unless the same pull request deliberately changes the architecture,
executable structure tests, schemas, and documentation together.

## Executable constraints

- Dependencies point inward: CLI to adapters/application, adapters to application/protocol/domain,
  application and protocol to domain, and domain to no project layer.
- Internal modules import defining modules directly. Only external consumers and package facade
  modules import from `pyghostboard.domain` or `pyghostboard.application`.
- Adapter modules do not import sibling adapters, and the internal import graph has no cycles.
- Domain modules do not perform file, environment, process, clock, configuration, or logging I/O.
- AI wire schemas never include private snapshots, private events, or private pieces.
- Public facade exports are explicit, unique, and resolvable.

These constraints are enforced by `tests/structure` and Import Linter. Run:

```shell
uv run pytest tests/structure
uv run lint-imports
```

## Review-only constraints

The following depend on deployment or human judgment and cannot be proven by repository tests:

- A trusted host is the only process allowed to persist or inspect complete match state. Operating
  system users with debugger privileges are outside the isolation boundary.
- External `MatchStore` implementations must make revision comparison, snapshot replacement, and
  event append one atomic transaction.
- Public names and error wording require an API usability review; passing an import test alone does
  not make a name clear or stable.
- GitHub must enforce protected `develop` and `main` branches, required checks, and human review.
- Short-lived branches target `develop` and are squash-merged. Only `develop` opens a release pull
  request to `main`; automation must not bypass the human review gate.
- A release tag is created only after the main push CI succeeds. The tag must identify the current
  main commit, and the release workflow injects that complete commit SHA into distributions. It
  stores verified wheel and source archives as Actions artifacts and does not publish them to a
  package registry.

When one of these constraints is relevant, state how it was reviewed in the pull request rather
than claiming it was covered by an automated test.
