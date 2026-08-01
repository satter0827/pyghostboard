# Design

These documents define the released pyghostboard system. They use present tense for implemented
behavior and keep unresolved alternatives in [notes](../notes/README.md).

Read them in lifecycle order:

1. [Requirements](requirements.md) defines users, scope, functional requirements, and quality
   requirements.
2. [Domain](domain.md) defines Geister rules, state, invariants, and deterministic transitions.
3. [Architecture](architecture.md) assigns responsibilities and dependency boundaries.
4. [Interfaces](interfaces.md) defines the Python, CUI, configuration, persistence, recording, and
   AI integration contracts.
5. [Quality](quality.md) defines verification, compatibility, and security controls.
6. [Delivery](delivery.md) defines change integration, versioning, and release artifacts.
7. [Operations](operations.md) defines runtime handling, failure recovery, support, and retirement.
8. [Lifecycle](lifecycle.md) maps requirements and activities to automated and human evidence.

## Terminology

- **Trusted host**: the process that owns complete match state and may inspect private values.
- **Player view**: the projection that contains everything one player may observe and no opposing
  ghost kinds.
- **Agent policy**: a transport-independent decision strategy that receives public rules and
  player-safe values.
- **Private record**: a replay file containing complete hidden match events.
- **Public event**: a display-safe projection that can be logged without revealing a live hidden
  placement.
- **Release artifact**: the verified wheel and source archive produced from a version tag on the
  current `main` commit.

Functional requirements use identifiers of the form `FR-###`. Quality requirements use
`QR-###`. The identifiers remain stable when wording becomes clearer; a behavior change receives
an explicit requirement change and matching implementation evidence.
