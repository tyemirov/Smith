# Orchestration Lifecycle Policy

## Scope And Authority

Apply this policy for model adoption, host changes, orchestration changes, rollout, rollback, and retirement.
Keep shared roles and model assignments in [the runtime contract](../agents/runtime.yaml).
Use [the orchestration guide](orchestration.md) for current installation commands.

Agents own documentation research, qualification tests, result interpretation, and recommendations.
The user supplies product decisions and any missing authorization.
Keep test execution with agents in every case.
Use existing task authorization and access for bounded tests.
Before a material increase in expense or task scope, obtain the missing authorization.
Keep approval-policy changes under their separate authority.

## Review Triggers

Start an assessment when the maintenance request identifies one of these conditions:

- A candidate model or model deprecation affects a current role.
- A host update changes agent configuration or delegation behavior.
- Repeated orchestration failures show a possible policy or adapter defect.
- Measured overhead exceeds the value of a required review or delegated role.
- Native orchestration supplies a possible replacement for part of this module.
- The user requests simplification or retirement.

A release announcement starts an assessment. Qualification evidence controls the recommendation.
This policy defines on-demand maintenance. It creates no recurring monitoring task.

## Agent-Owned Qualification

1. Record the affected role, current assignment, candidate assignment, and intended benefit.
2. Retrieve current primary documentation for the exact candidate and destination host.
3. Verify account availability, supported effort, required tools, and configuration compatibility.
4. Record the small task set and authorized time and expense limits before comparative runs.
5. Give both assignments the same inputs, task rules, and expected results.
6. Run tests through available native delegation, CLIs, repository checks, simulators, emulators, or automated browsers.
7. Record the requested and actual model, effort, permissions, agent identifier, and execution method when exposed.
8. Compare correctness, missed issues, false findings, instruction adherence, completion time, and observable cost.
9. Request an independent review when the shared architect checkpoint applies.
10. Record an adoption recommendation, retention recommendation, or specific evidence limit.

Use plans and patches with known weaknesses for architect comparisons.
Use known repository questions for explorer comparisons.
Use bounded implementation tasks with existing acceptance tests for worker comparisons.
Use questions with primary-source answers for researcher comparisons.

When native tests or model metadata are unavailable, report the evidence limit.
Keep unverified observations separate from verified results.
Continue independent checks that remain available.
Keep the current assignment when the necessary promotion evidence is unavailable.
Ask the user only for a missing decision or authorization.
Keep qualification execution with agents instead of assigning tests to the user.

## Decision Record

Record these fields in the maintenance evidence:

- Change scope: model assignment, host adapter, orchestration policy, or module retirement.
- Exact host, profile roots, current assignment, and candidate assignment.
- Documentation sources and retrieval dates.
- Comparison inputs, expected results, observed results, and evidence paths.
- Actual model and effort evidence, with unavailable metadata identified.
- Time, observable cost, and authorized limits.
- Recommendation, reasons, uncertainty, and independent review findings.
- Applicable authorization, installation result, and remaining work.

## Promotion Criteria

For a model change, require the following evidence:

- The destination host supports the candidate assignment and required tools.
- The candidate preserves required task behavior and authority boundaries.
- The comparison shows the intended benefit within the authorized limits.
- Required validation and independent reviews are completed.

Change the host binding when the responsibility stays the same.
Change the adapter when the host configuration contract changes.
Treat removed checks or changed delegation authority as explicit policy decisions.
Use the user request or standing policy to determine promotion authority.

## Profile Rollout

Treat `.codex` and `.codexw` as separate installations.
Include every affected coding host and profile root in the rollout record.
Inspect profile overrides and invocation flags before effective-model acceptance.
Preview, install, and check each selected root explicitly.
Verify actual delegation metadata in a new session when the host requires one.
Report partial completion when one profile remains unresolved.
Preserve unrelated configuration and subsequent user edits.

## Retirement Criteria

Evaluate retirement at the smallest useful scope: role, checkpoint, host adapter, or orchestration module.
Require evidence that the proposed replacement covers the retained task responsibilities and authority boundaries.
Compare the replacement with the current behavior through agent-run tests.
Resolve every dependent workflow before removal.
Record the replacement or the authorized primary-agent execution method.
Record any authorized removal of a required capability as an explicit policy decision.

Retirement affects orchestration-owned role files, instruction sections, configuration values, and dependent role references.
Preserve Governor repository policies, normalization tools, and unrelated global instructions.
Record retired scope so later installation respects the retirement decision.

## Current Tooling And Required Extensions

The current installer supports preview, installation, consistency checks, and restoration after a write error within one process.
It records generated file hashes and the source path.
It does not implement durable rollback, fleet transactions, immutable installed revisions, or retirement reconciliation.
Deployment exclusions select future installation targets. They do not remove installed outputs.
The current renderer uses fixed roles and checkpoints.

Partial role or checkpoint retirement requires a contract and renderer change.

Installed instructions currently reference mutable source files.
A lifecycle-policy edit can affect agent guidance before another installation.
An installed profile does not yet capture an immutable policy revision.

Implement the following extensions before relying on automated rollout or retirement:

- A profile inventory with explicit host roots and effective overrides.
- Immutable revisions that include the contract, renderer, and referenced policy files.
- Receipts for owned files, instruction sections, and changed configuration keys.
- Prior and applied state for each owned operation, with subsequent-edit conflict detection.
- Retention of the current revision and one previous revision, with automatic cleanup of older recovery state.
- Workflow migration and owned-output removal for an explicit retired state.
- Public command tests for promotion, partial failure, rollback, conflicts, and retirement.

Keep these extensions inside the public Agent Runtime package and installer.
