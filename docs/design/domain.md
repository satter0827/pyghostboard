# Domain

## Standard rules

A standard match uses a six-by-six board. Each player places four good and four bad ghosts in its
eight starting squares. A normal action moves one owned ghost by one orthogonal square into an
empty square or a square occupied by an opposing ghost. Moving onto an opposing ghost captures it.

A player wins by moving a good ghost through one of that player's exits, capturing all opposing
good ghosts, or having all of its own bad ghosts captured. The configured rule set may enable a
subset of these built-in victory conditions.

## Configurable rules

`RuleSet` is strict, immutable, and data-only. It contains the format version, board dimensions,
piece counts, starting squares, exits, shared movement vectors, and victory conditions. Validation
rejects out-of-board squares, duplicate or overlapping regions, missing exits, duplicate movement
vectors, zero movement, invalid counts, and an empty victory-condition set.

Movement applies equally to every ghost. A rule cannot select movement by a hidden ghost kind,
because legal actions must remain independent of the opponent's private assignment.

## State and values

Domain values are immutable and reject unknown fields. `Match` owns the complete trusted state.
`PrivatePiece` records owner, kind, location, and removal information. A removed piece retains its
last square and whether it was captured or escaped so restoration can validate the transition.

`PlayerView` uses different shapes for owned and opposing pieces. Owned pieces contain their kind
and square. Live opposing pieces appear only as occupied squares. Captured pieces may reveal kind
because capture makes that information public.

## Transitions

`Match.start()` validates both secret placements and creates revision zero. `Match.play()` accepts
the current player and a legal `Move` or `Escape`, then returns a new match and its private event.
It does not mutate the prior match.

Each successful action increments the revision and advances the turn unless it finishes the
match. A finished match rejects additional actions. Illegal ownership, turn, source, destination,
capture, escape, or outcome combinations fail explicitly.

`Match.snapshot()` produces a versioned private persistence value. `Match.restore()` validates all
derived invariants, including revision, turn, removals, escape squares, and outcome. Replay applies
versioned private events through the same transition rules and rejects mismatches.

## Reproducibility

Domain events contain no clock values. Random choice belongs to an injected or external policy,
and the host gives each AI a deterministic seed. Information-set MCTS samples hypothetical hidden
assignments from a player view and never receives the trusted snapshot. Tests use fixed seeds,
search iterations, and rollout limits rather than elapsed time. The same validated inputs therefore
produce the same policy decisions and domain transition stream.
