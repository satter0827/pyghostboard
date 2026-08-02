# Operations

## Operating model

pyghostboard is a local Python package and process, not a hosted service. Operations cover
installation, configuration, AI subprocess handling, private record custody, release-artifact
retention, support, and retirement. Service monitoring, backups, accounts, and production database
operation remain outside the 0.1 series.

## Installation and configuration

Install a verified wheel or a source checkout on a supported Python and platform combination.
Validate custom rules before starting a match. Supply runtime limits through documented
`PYGHOSTBOARD_` environment variables and keep secrets out of rule files and command arguments.
`PYGHOSTBOARD_LANGUAGE` may contain `en`, `ja`, or a locale-qualified form such as `ja_JP`. An
unsupported value falls back to English; `--language` takes precedence for one invocation.

## Match failures

The host reports typed failures for invalid rules, illegal actions, missing matches, revision
conflicts, AI protocol violations, timeouts, abnormal exits, and maximum plies. An aborted match
does not promote its temporary private record. Retry only after correcting configuration or
replacing the failed AI; do not treat partial output as a valid replay.

## Logs and private records

Diagnostic logs contain public event projections and operational failures. Private records contain
both players' hidden information and require secret-file handling. Store records only at an
explicit destination with directory permissions appropriate for the host user. Use explicit
overwrite only when replacement is intended.

If record confidentiality may have been lost, restrict access to the affected file, preserve the
minimum evidence needed for investigation, and follow the [security policy](../../SECURITY.md).
Repository automation cannot determine external storage permissions or exposure impact; a human
owner performs and records that assessment.

## Arena results

Create every arena run at a new path. `arena run` refuses an existing output directory. `arena
resume` acquires the same exclusive lock, rejects a completed run, validates the saved configuration
and durable attempts, requires the saved package version and source commit to match the current
installation, and executes only missing indexes. A failed attempt is evidence and is not retried
automatically.

The root and each attempt directory use mode `0700`; configuration, manifest, lock, result, and
private record files use mode `0600`. Each attempt directory appears only after its result and
optional complete record are synced and atomically promoted. A `completed` manifest means every
planned attempt has one durable result, including failures. An interrupted directory may be
analyzed but should not be treated as the planned sample size.

The complete arena directory is private because `config.json` contains external commands,
`result.json` may contain process details, and `match.jsonl` contains hidden state. The table and
JSON produced by `arena analyze` omit those fields. Move or archive the directory as one private
unit; share only the sanitized analysis after reviewing agent identifiers and declared revisions.

## Release artifacts

GitHub Actions retains verified wheel and source archives. A maintainer confirms that the tag SHA
equals the current main SHA, the Release Artifact workflow succeeded, and the artifact contains the
expected two archives before treating the version as released. Artifact retention duration and
download access depend on repository settings and require periodic human review.

## Support and security

The latest `0.1.x` source release and latest `main` revision receive security fixes. Vulnerabilities
use GitHub private vulnerability reporting and never public issues or pull requests. A human
maintainer evaluates impact, coordinates remediation and disclosure, and records the supported
version in the security policy.

## Deprecation and retirement

An incompatible Python API or wire-format change documents its replacement and affected versions
before release. Versioned persisted data and protocol formats are not silently reinterpreted.

Retiring a version requires a changelog entry, an updated security support statement, and a clear
replacement or end-of-support notice. Removing retained artifacts or private records is a manual,
destructive operation performed only by their owner under the applicable retention policy.
