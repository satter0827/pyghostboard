# Review Gate

Review changes that require analysis rather than repeating deterministic checks from the Release
Gate. Codex performs the first review. A human evaluates each finding, resolves the discussion, and
decides whether to merge.

## Review scope

- Confirm that public APIs, configuration, errors, and migration guidance are understandable and
  consistent with the intended use.
- Confirm that responsibilities remain in the correct architectural layer and that new abstractions
  have a concrete boundary or at least two callers.
- Look for ways private match state, opposing ghost kinds, credentials, or record paths could cross
  a trust boundary.
- Analyze process, persistence, concurrency, and release failure modes that repository tests cannot
  prove in every deployment.
- Identify missing operational or compatibility information that would cause a user to apply the
  change incorrectly.

Do not report formatting, lint, typing, coverage, generated-file, packaging, or dependency-audit
results. Those belong to the Release Gate.

## Finding requirements

Each finding states its severity, the concrete failure condition, the affected file and location,
and the required correction. Do not report preferences, hypothetical concerns without a reachable
failure, or claims without repository evidence.

The review applies to the latest materially changed commit. After a corrective push, request
another Codex review only when the change invalidates the prior analysis. Resolve a valid finding
after the correction is present. Resolve a false positive only after recording why its failure
condition cannot occur.

Merging the pull request records the human decision. No AI score, label, or additional approval
marker replaces that decision.
