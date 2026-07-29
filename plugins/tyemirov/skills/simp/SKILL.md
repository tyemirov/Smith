---
name: simp
description: Audit a repository for simplification opportunities and, only when explicitly requested, apply small simplifications that preserve the current supported functionality contract. Use for repo-wide complexity reduction, duplication removal, abstraction cleanup, dependency reduction, and maintainability improvements under a forward-only contract with no legacy support, fallbacks, or compatibility shims.
---

# Functionality-Preserving Repository Simplifier

Simplify the repository while preserving its current supported functionality.

Treat simplification as the optimization objective and the repository's current
canonical contract as the constraint. Do not preserve accidental behavior,
obsolete paths, or stale assertions merely because they are observable.

## Invocation

Read the mode and scope from the user's instruction. A host may deliver that
instruction through a slash command, a named skill mention, or semantic skill
activation.

- `audit [scope]`: review only and return a ranked report. This is the default.
- `annotate [scope]`: review only and write or update
  `SIMPLIFICATION_AUDIT.md` at the repository root.
- `apply [scope]`: apply only candidates that pass every retention gate below.
- `scope` may be a path, package, module, service, language, or `repo`.

Never infer `apply` from a general request to simplify, clean up, improve, or
refactor. Enter `apply` mode only when the user explicitly selects `apply` as
the mode. Resolve a path scope inside the current repository root; reject a
scope that escapes the repository.

## Contract authority

Establish one current contract before evaluating candidates. Use this authority
order:

1. Binding repository instructions such as `AGENTS.md` and `CLAUDE.md`
2. Current architecture, product, API, schema, and operational documentation
3. Current build, deployment, package, and configuration manifests
4. Active supported callers, integrations, and deployment paths
5. Tests, examples, fixtures, and issue history that agree with the authorities
   above

Tests and documentation are evidence, not automatic retention obligations.
When they encode a rejected or obsolete contract, classify them as stale and
remove or update them with the obsolete implementation in `apply` mode.

## Forward-only discipline

Preserve only the current supported functionality contract.

Do not create, retain, or restore:

- Deprecated APIs, commands, configuration, schemas, or persisted shapes
- Legacy aliases, adapters, wrappers, or translation layers
- Fallback behavior or best-effort recovery for rejected inputs or old state
- Dual reads, dual writes, shadow paths, or old/new branching
- Downgrade paths, old-version negotiation, or compatibility shims
- Tests, examples, fixtures, or documentation whose only purpose is to preserve
  an obsolete contract

A one-off data migration is allowed only when the user or repository contract
explicitly requires a bounded move into the current canonical schema. After the
migration, remove the bridge and retain only the current shape.

## Current functionality inventory

Functionality includes, where applicable:

- Current public APIs, exported symbols, type signatures, protocols, and
  extension points
- Current CLI commands, flags, defaults, stdout/stderr, prompts, and exit codes
- Current HTTP routes, status codes, headers, payloads, redirects, and streaming
- Canonical serialization formats, schemas, database effects, and data integrity
- Current configuration keys, environment variables, defaults, precedence, and
  feature flags
- Authentication, authorization, validation, privacy, security controls, and
  auditability
- Error types, error boundaries, retry behavior, timeouts, cancellation, and
  idempotency
- Side effects, ordering, concurrency semantics, transactions, and consistency
- Accessibility behavior and current user-visible interaction flows
- Logging, metrics, tracing, and operational hooks used by current operators
- Performance, memory, latency, startup, and resource ceilings when contractual
  or operationally significant
- Build, packaging, installation, deployment, plugin, and integration behavior
  for current supported targets

Do not assume untested current functionality is disposable. Missing tests lower
confidence; they do not prove irrelevance.

Never remove validation at a trust boundary, authorization checks, error
handling that prevents data loss, security controls, accessibility behavior, or
operational safeguards merely because they look repetitive.

Do not modify generated, vendored, lock, migration-history, snapshot, fixture,
or third-party code unless the repository's current documented workflow
requires it. Historical migration files may be current build inputs; active
runtime bridges for old shapes are not protected.

## Core principle

Every retained change must carry evidence for both claims:

1. It makes the implementation materially simpler.
2. It preserves the applicable current functionality contract.

If either claim is uncertain, report the candidate and do not modify it.

## Phase 1: Establish repository context

Before proposing changes:

1. Read all repository instructions and directly referenced files, including
   `CLAUDE.md`, `AGENTS.md`, READMEs, contribution guides, build files, CI
   configuration, API specifications, schema files, and package manifests.
2. Identify languages, applications, libraries, services, generated areas,
   deployment units, and repository boundaries.
3. Determine canonical build, test, lint, type-check, formatting,
   static-analysis, integration-test, and end-to-end commands.
4. Inventory current public and operational surfaces using
   `references/behavior-contract.md`.
5. Explicitly inventory deprecated, legacy, fallback, dual-path, and old-shape
   code that lies outside the current contract.
6. Record the current revision and complete working-tree state. Never overwrite
   unrelated user changes.
7. Run the strongest practical baseline checks before editing. Record
   pre-existing failures exactly; do not disguise them by changing tests or
   weakening checks.
8. For important current functionality lacking tests, create a proposed
   characterization-test plan. In `apply` mode, add focused characterization
   tests before changing the implementation when practical.

### Audit-mode command isolation

`audit` mode must leave the repository exactly as it found it.

- Run only checks documented as non-mutating in the live worktree.
- Redirect caches and build outputs to run-owned temporary paths when supported.
- Run potentially mutating checks in an isolated checkout when practical.
- Compare the complete working-tree state after every check.
- If a command cannot be isolated or its write behavior is uncertain, skip it
  and mark the affected verification as unavailable.
- Never clean, reset, checkout, or delete pre-existing or unattributed files.

If the repository cannot build or test, continue in audit mode and mark all
affected findings as unverified. Do not apply changes based only on visual
plausibility.

## Phase 2: Parallel repository review

When subagents are available, run independent reviewers in parallel. Give each
reviewer the repository instructions, requested scope, current-contract
summary, baseline status, and the requirement to return evidence rather than
edits.

### Reviewer A: Reuse and duplication

Find:

- Reimplemented helpers already available elsewhere in the repository
- Near-duplicate code paths that can use one current implementation
- Repeated parsing, validation, formatting, conversion, or error handling
- Local utilities that duplicate a standard-library or approved dependency

Reject consolidation when paths have materially different current contracts,
ownership, release cadence, security boundaries, or independent evolution.

### Reviewer B: Control and data flow

Find:

- Excessive nesting and avoidable branches
- Redundant state, temporary values, conversions, or passes
- Equivalent conditionals that can be expressed more directly
- Dead code proven unreachable by references, build configuration, and current
  supported runtime paths
- Deprecated, legacy, fallback, dual-path, and old-shape branches outside the
  current contract
- Control flow that can become linear without changing current ordering,
  errors, cancellation, or side effects

Treat concurrency, deferred cleanup, transactions, retry loops, and ordering as
high risk.

### Reviewer C: Abstractions and dependencies

Find:

- Interfaces or factories with one implementation and no current extension
  contract
- Wrapper layers that add no current policy, observability, isolation, or test
  seam
- Configuration or feature flags dead across current supported deployments
- Dependencies replaceable by a stable standard-library or platform capability
- Abstractions whose removal shortens the path from caller intent to behavior
- Adapters, aliases, and translation layers retained only for obsolete callers

Do not collapse current public extension points, security boundaries, or
architectural seams without direct evidence that they are unsupported and
unused. Obsolete bridges are simplification targets, not protected seams.

### Reviewer D: Efficiency without functional drift

Find:

- Repeated work, unnecessary allocation, duplicate I/O, and avoidable
  transformations
- Multiple passes safely reducible to one
- Cache or batching layers that are redundant rather than functionally
  meaningful
- Simpler algorithms with equal current semantics and acceptable complexity

Do not alter current timing, ordering, memory bounds, backpressure, rate
limiting, retries, or consistency semantics without explicit proof.

### Reviewer E: Adversarial functionality verifier

This reviewer does not seek simplifications. It tries to falsify each proposed
candidate.

For every candidate, ask:

- Which current supported caller, user, integration, deployment, or edge case
  could observe a functional difference?
- Is the claimed invariant part of the current canonical contract, or merely an
  accidental or obsolete behavior?
- Could errors, logs, timing, ordering, cancellation, persistence,
  serialization, or permissions change for current supported flows?
- What test would distinguish the current and proposed implementations?
- Do any tests or fixtures being used as evidence encode a stale contract?
- Is the evidence sufficient to classify the candidate as proven, testable, or
  unsafe?

The verifier may reject a candidate even when all simplification reviewers
favor it. Independent verification means a fresh reviewer that did not design
the candidate; self-review does not satisfy this requirement.

## Phase 3: Reconcile findings

Deduplicate and reconcile all findings. Reject:

- Style-only churn with no meaningful reduction
- Speculative dead-code claims
- Abstractions that merely look verbose but encode current policy or boundaries
- Changes that rewrite tests to accept functional drift
- Large rewrites whose current-functionality preservation cannot be reviewed
  locally
- Dependency substitutions with uncertain current platform, licensing,
  operational, or maintenance effects
- Suggestions already implemented elsewhere in the branch
- Findings that conflict with repository instructions

Tests that exclusively assert an obsolete contract are not a veto. Classify
them as stale evidence and remove them with that contract in `apply` mode.

Classify each surviving candidate:

- `PROVEN`: current-functionality preservation follows from local reasoning plus
  existing checks.
- `TESTABLE`: preservation can be established with specific characterization or
  differential tests.
- `UNSAFE`: current functionality may change or evidence is insufficient.
- `BLOCKED`: potentially valid, but baseline, environment, ownership, or tooling
  prevents verification.

## Required finding format

For every candidate include:

- ID
- Rank
- Classification
- Confidence
- Location
- Current structure
- Proposed simplification
- Current functionality that must remain invariant
- Current-contract evidence
- Obsolete paths removed, if any
- Proof obligations
- Verification commands or tests
- Risk and likely blast radius
- Estimated reduction: lines, branches, abstractions, dependencies, or
  duplicated paths
- Recommended action

Use `templates/SIMPLIFICATION_AUDIT.md`.

## Audit and annotate modes

In `audit` mode:

- Make no repository changes.
- Return the executive summary and highest-value findings.
- Include baseline failures and coverage limitations.
- Prefer a small number of strong findings over a large speculative list.

In `annotate` mode:

- Make no source-code changes.
- Write or update `SIMPLIFICATION_AUDIT.md`.
- Use file-and-line references rather than source comments.
- Preserve prior unresolved entries when they remain valid; mark resolved or
  obsolete findings explicitly so the audit trail remains clear.

## Apply mode

Apply only `PROVEN` candidates and `TESTABLE` candidates whose required tests
are first added and passing.

Process candidates one at a time in descending value-to-risk order:

1. Confirm a candidate-specific rollback boundary and preserve unrelated
   working-tree changes. Block if the same files contain unrelated edits.
2. Run the candidate's focused pre-change checks.
3. Add characterization or differential tests for current functionality when
   required.
4. Make the smallest coherent implementation change, deleting obsolete code
   rather than adding a bridge.
5. Remove tests, fixtures, examples, and documentation that exclusively encode
   the deleted obsolete contract.
6. Run formatting and focused tests.
7. Run the repository's strongest practical full verification set.
8. Compare current public surfaces, generated outputs, schemas, snapshots, CLI
   help, API specs, and other current contract artifacts where relevant.
9. Ask an independent verifier to review the final diff against the current
   functionality contract.
10. Retain the patch only if every retention gate passes.
11. Otherwise restore only this candidate from its candidate-specific snapshot
    and record why it failed. Never use broad reset or checkout commands.

Do not batch unrelated candidates into one patch. Do not opportunistically fix
unrelated bugs or restyle surrounding code.

## Retention gates

A candidate may remain applied only when all applicable gates pass:

1. **Current contract:** No current supported capability is removed or weakened.
2. **Baseline:** No previously passing check regresses.
3. **Characterization:** Relevant current edge behavior is covered before
   structural change when existing coverage is insufficient.
4. **Current public surface:** Current APIs, CLI, schemas, configuration,
   persistence formats, permissions, and error contracts remain intact unless
   the user explicitly approves a named functional change.
5. **Operational behavior:** Required current logging, metrics, tracing,
   performance bounds, ordering, cancellation, and reliability remain intact.
6. **Independent verification:** A fresh verifier focused on functional drift
   finds no plausible unaddressed change. If no independent verifier is
   available, classify the candidate `BLOCKED`.
7. **Measurable simplification:** The result removes meaningful complexity,
   duplication, indirection, dependency surface, or maintenance burden.
8. **Reviewability:** The diff is small enough for a human to reason about
   locally.
9. **Rollback:** The change has an isolated rollback path that cannot overwrite
   unrelated work.
10. **No test weakening:** Tests for current functionality, assertions,
    snapshots, and thresholds were not relaxed merely to make the change pass.
    Removing tests that exclusively encode a rejected obsolete contract is
    required cleanup, not weakening.
11. **Forward-only result:** No alias, fallback, dual path, old-shape reader, or
    transitional bridge remains after the candidate is retained.

Failure of one gate means restore the candidate or report it only.

## Stop conditions

Stop applying changes and switch to report-only when:

- Baseline current functionality cannot be established
- The repository has material unrelated uncommitted changes in the same files
- A candidate crosses service, storage, security, or current support boundaries
  without adequate integration tests
- Verification requires unavailable credentials, infrastructure, data,
  hardware, or external systems
- An independent verifier is unavailable
- The proposed simplification becomes a rewrite
- Reviewers disagree about current semantics and a focused test cannot resolve
  the disagreement
- The expected reduction is minor relative to functional risk

## Final response

Report:

1. Scope reviewed
2. Current contract and explicitly obsolete surfaces
3. Baseline and limitations
4. Candidate counts by classification
5. Applied candidates, if any
6. Verification performed
7. Restored or rejected candidates and reasons
8. Remaining highest-value opportunities
9. Exact files changed
10. Current functionality that could not be verified

Never claim preservation of current supported functionality beyond the evidence
available.
