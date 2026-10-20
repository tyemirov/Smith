# Independent review subagent: integration, evidence, and gates

## Codex installation

`codex/agents/whip_reviewer.toml` is a **deployable custom-agent definition**. The shared Smith installer installs it with the skill. Standalone and plugin installations require the copy step below. Copy it to `.codex/agents/whip_reviewer.toml` in the target repository (or `~/.codex/agents/` for personal use). Current Codex loads custom agents at those paths. No model is pinned; it inherits the parent model and reasoning settings. Review is read-only **by instruction**; custom agent TOML does not enforce separate filesystem permissions. Set parent sandbox policy appropriately.

For substantial rewrites, the parent editor delegates to the named `whip_reviewer` **after** producing the candidate and mechanical report, then waits for the full result. Use a separate fresh agent context and give direct access to all source artifacts. Example prompt:

> Invoke `whip_reviewer` to independently audit the revision. Read `approved.md`, `session.md`, `candidate.md`, `ledger.json`, `change-plan.md`, `source-map.md`, and `mechanical-report.json`. Reconstruct baseline facts yourself before inspecting ledger coverage. Return the exact JSON review report specified by the whip skill. Do not edit any files. Wait for the review before deciding whether to promote the candidate.

Where the platform supports delegation without named custom agents (for example, some ChatGPT Work sessions), instruct the parent to spawn an independent reviewer subagent with the complete review protocol below. For environments with **no available subagents**, the parent may perform a provisional review, but **must mark independent semantic gate PENDING**. Do not pretend a new context was created.

The parent saves the reviewer output to `reviewer-report.json` and uses `scripts/gate_review.py` with the mechanical report and ledger; its verdict can only be *stricter*, never a substitute for inspecting the evidence. The parent does all repairs and asks for a fresh independent check on the repaired candidate.

## Inputs

- Immutable last approved baseline, including version identity.
- Immutable session-start baseline.
- Entire candidate revision, including tables/appendices/citations and native structures if any.
- Ledger with stable IDs and source anchors.
- Authorized change plan, with explicit user-directed semantic changes and source-to-destination mapping.
- Mechanical regression report (`scripts/check_revision.py`), where supported.

If approved and session baselines differ, reconcile later *authorized* changes. A baseline's presence is not evidence that all its claims are still intended to be current.

## Output JSON schema (contract)

Keys required at top level:

```json
{
  "schema_version": "1.0",
  "review_completed": true,
  "verdict": "PASS",
  "baseline_refs": {"approved": "approved.md#sha256:...", "session": "session.md#sha256:...", "candidate": "candidate.md#sha256:..."},
  "ledger_reviews": [
    {
      "id": "F-001",
      "status": "preserved",
      "source_anchor": "approved.md#Goals",
      "source_quote": "$400,000 annually",
      "candidate_anchor": "candidate.md#Goals",
      "candidate_quote": "$400,000 annually",
      "authorized_change_id": null,
      "reasoning": "Same annual target and currency."
    }
  ],
  "unmapped_baseline_units": [],
  "unreviewed_new_claims": [],
  "citation_issues": [],
  "findings": [],
  "limitations": [],
  "warning_dispositions": [{"code": "SEMANTIC_REVIEW_REQUIRED", "reason": "Independent semantic review completed and supported by the ledger evidence"}]
}
```

Allowed `ledger_reviews[].status`: `preserved`, `moved`, `rephrased-equivalent`, `authorized-change`, `missing`, `contradicted`, `uncertain`. For an `authorized-change` provide `authorized_change_id` matching an explicit change in the ledger/change plan and evidence for the modified or deleted claim. Use `candidate_anchor` and `candidate_quote` set to `null` for authorized deletions, and explain the exact permission.

For **every** ledger item include one `ledger_reviews` entry. `unmapped_baseline_units` includes any material assertion omitted from the ledger, with a location and quote. `unreviewed_new_claims` holds new candidate claims whose provenance or authorization remains unresolved. `citation_issues` holds citation mismatches or unsupported references. `findings` contains confirmed problems, severity (`critical`, `high`, `normal`), baseline and candidate anchors/quotes, and repair suggestion. `limitations` records missing sources, partial document coverage, ambiguous approvals, and other obstacles. `warning_dispositions` records an evidence-based explanation for **each distinct warning code** from the mechanical report (including number drift, unpinned baseline identity, or semantic review required).

**Evidence rule**: `source_quote` and `candidate_quote` must be actual short excerpts from inspected documents; avoid invented quotations. Anchors must identify a file version/section/table or native element. Do not mark a claim preserved when evidence is missing. The checker verifies that evidence fields are populated; **it cannot determine whether the quotes actually appear in the documents or whether they mean the same thing**. Parent must verify the evidence independently when risk is high.

`verdict`: `PASS` (all gates cleared), `FAIL` (proven unauthorized regression), `PENDING` (missing evidence or unresolved semantic question). A `PASS` must have empty unresolved lists and zero `missing`, `contradicted`, or `uncertain` ledger statuses.

## Acceptance

1. Mechanical gate `PASS` (warnings adjudicated).
2. Independent reviewer report completes, covers every ledger entry and independently audits omitted source units and new candidate assertions.
3. `uv run --script scripts/gate_review.py --ledger ledger.json --mechanical mechanical-report.json --review reviewer-report.json --approved approved.md --session session.md --candidate candidate.md --report release-gate.json` returns 0.
4. Parent inspects report and traceability; it can still reject even on a machine `PASS`.
5. Only then does parent promote candidate. Any repair triggers re-review of the revised candidate (and affected dependent claims). Never reuse an earlier PASS against a changed candidate.

The release-gate checker validates fingerprints, review coverage, reported quotes, authorization IDs, and warning disposition. It cannot verify logical equivalence or the truth of cited material. For native rich-text documents, review full native content and provider versioning; the Markdown-specific checker may not apply.
