# Application integration

## Rules

`RuleSet` is an immutable Pydantic model. Import it from `pyghostboard.domain`; load TOML only in an
adapter or application entry point. A complete example is available at `examples/rules.toml`.
Customization is data-only and shared movement vectors cannot depend on a hidden ghost kind.

## Persistence

Implement the async `MatchStore` protocol from `pyghostboard.application`. `load(match_id)` returns
a private snapshot or `None`. `commit(snapshot, events, expected_revision=...)` must perform the
revision comparison, snapshot replacement, and event append in one transaction. Creation expects
revision `-1`; later commits expect the revision that was loaded. A conflict raises
`RevisionConflict` and must not partially write.

`MatchService` owns create, load, player-view, transition, persistence, and public diagnostic event
projection. Database adapters should serialize with the versioned domain codecs and call
`Match.restore()` when reading so persisted invariants are checked again. Keep database libraries
outside `domain` and inject the store into the service.

## Logging and records

Inject an `EventLogger` compatible logger into `MatchService`. The application logs only projected
public events; do not log `PrivateMatchSnapshot`, `PrivateMatchEvent`, `Placement`, or a complete
model dump. The CUI's default renderer emits WARNING-and-higher JSON to standard error with an RFC
3339 UTC timestamp.

JSON Lines records are different from diagnostic logs: they deliberately contain complete private
events for deterministic replay. Treat record files as secrets. Their header identifies the record
format, distribution version, and complete main commit SHA. `MatchRecorder` creates mode `0600`
temporary files, refuses destination overwrite by default, and promotes only after successful match
completion.

## Distribution

The repository builds wheel and source archives in standard Python formats but does not publish
them to a package registry. A release tag must point to the current `main` commit after main CI has
passed. The tag workflow injects that commit SHA, asserts exact artifact names and metadata, runs
`twine check`, and stores the files as a GitHub Actions artifact.
