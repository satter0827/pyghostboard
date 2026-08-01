# Documentation

pyghostboard keeps temporary investigation separate from the design that governs released
behavior.

## Document sets

- [Design](design/README.md) defines the product requirements, domain, architecture, interfaces,
  quality controls, delivery process, and operating responsibilities. Design documents describe
  behavior that exists in the released system.
- [Notes](notes/README.md) hold temporary research and unresolved choices. Notes are not part of a
  release and do not define supported behavior.

The repository root contains documents for specific audiences:

- [README](../README.md) introduces installation and supported use cases.
- [Contributing](../CONTRIBUTING.md) gives contributors executable development steps.
- [Security policy](../SECURITY.md) gives vulnerability reporting and support instructions.
- [Changelog](../CHANGELOG.md) records user-visible changes by release.

## Authority

Executable public contracts take precedence over explanatory documents. Versioned JSON Schemas
and the installed Python API define their respective machine-readable interfaces. Design documents
explain the system-level constraints that connect those contracts. Audience guides summarize the
design without replacing it.

When a contract changes, update its implementation, tests, generated Schema when applicable, and
the affected design document in one pull request. Keep proposals in notes until the decision and
implementation are ready to move together.
