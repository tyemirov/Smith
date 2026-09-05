# Behavior Evaluation

Use this evaluation after changes to hierarchy rules or model assignments.
The scanner tests in `run_evals.py` test helper behavior, not agent decisions.

## Procedure

1. Give a fresh evaluating agent `SKILL.md` and `hierarchy-cases.json`.
2. Give the agent access to the skill's referenced instructions.
3. Request an answer to each case from its synthetic inventory.
4. Require a read-only response. Keep provider calls and actual folder operations outside the evaluation.
5. Keep this rubric and prior answers out of the evaluating agent's context.
6. Evaluate the returned paths, decisions, and model plan against the rubric below.
7. Record the skill revision, host capabilities, evaluation method, and result outside the source tree.

## Acceptance Rubric

| Case | Required behavior |
| --- | --- |
| `related-roots` | Compare separate roots with a clear shared parent for Developer Tools and Networking. Explain the selected hierarchy. |
| `related-roots` | Preserve Atlas internals and its cover. Keep independent Research separate from Projects. |
| `useful-depth` | Preserve the child, school, and year distinctions. Accept Assets within the named project. |
| `small-distinct-domain` | Keep Health easy to reach despite its single file. Preserve the project boundary. |
| `unavailable-review-model` | Allow the configured Scout. Report the unavailable Gatekeeper pair and keep dependent moves blocked. |

Accept equivalent folder names when their scope is clear.
A fixed root count or a specific umbrella name is not an acceptance requirement.
Require a documented hierarchy comparison, not consolidation in every case.
Require an explicit user decision before substitution for an unavailable model assignment.

## Limits

This evaluation tests instruction use with synthetic inputs.
It does not prove filesystem execution, provider access, or repeatability across all models.
Run the helper integration suite separately when helper behavior changes.
