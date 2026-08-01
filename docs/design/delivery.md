# Delivery

## Integration branches

`develop` is the integration branch. Short-lived branches start from the latest `origin/develop`,
target `develop`, and squash-merge after required checks pass. `main` contains release-approved
revisions and accepts pull requests only from `develop` with a merge commit.

Both branches prohibit direct pushes, force pushes, and deletion. Main validation uses GitHub's
test merge so a prior release merge commit does not require merging `main` back into `develop`.

## Continuous integration

Pull requests to `develop` and `main` run formatting, linting, strict typing, dependency contracts,
structure tests, unit tests, integration coverage, package construction, installation smoke tests,
and dependency auditing. Main pull requests and main pushes also run the supported Python and
operating-system compatibility matrix. Workflow actions are pinned to complete commit SHAs.

Dependabot opens weekly dependency pull requests against `develop`. Dependency audit network
failure is an environment failure and never counts as evidence that dependencies are safe.

## Versioning

Hatch derives development and release versions from Git. Public JSON formats carry independent
semantic versions because a package release does not necessarily change every wire format.
Incompatible format evolution receives a new versioned Schema and explicit compatibility policy.

## Release sequence

1. A maintainer reviews the integrated `develop` state and opens the only permitted release pull
   request to `main`.
2. GitHub validates the test merge, including compatibility and source-branch policy.
3. The maintainer merges through GitHub after every required check succeeds.
4. Main push CI validates the exact resulting commit.
5. The maintainer creates `vX.Y.Z` on that current `main` commit.
6. The tag workflow derives the exact version, injects the complete commit SHA, builds the wheel and
   source archive, verifies filenames and metadata, runs `twine check`, and uploads the archives as
   a GitHub Actions artifact.

The tag workflow does not publish to PyPI, TestPyPI, or another package registry. A successful main
merge approves source for release; successful tag-artifact validation completes the release.

## Source distribution

The source archive includes public project documents, formal design, examples, package source, and
build metadata. It excludes temporary design notes. The wheel contains runtime code, type markers,
public Schemas, the console entry point, version, and source provenance.
