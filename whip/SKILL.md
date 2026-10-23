---
name: whip
deployment:
  include:
    - all
description: Edit, reorganize, or comprehensively rewrite an existing document while preserving previously approved facts, decisions, arguments, citations, and untouched content. Use for iterative document revisions, major refactoring, consolidation, tracked editorial changes, and regression-sensitive editing. For one-off drafting from scratch, this skill is unnecessary.
compatibility: >-
  Text checks require uv and Python 3.10 or later. Substantial revisions require an independent subagent. Native documents require access through their editor or API.
---

# Whip: preserve what is already correct

Invoke this skill with `$whip`.

## Compatibility and prerequisites

- Text checks require `uv`, Python 3.10 or later, and the standard library.
- Keep `check_revision.py` and `gate_review.py` together for their local import.
- The text checkers have no native OS adapter or network client.
- Substantial revisions require a fresh independent subagent.
- Codex can use the bundled `whip_reviewer` definition.
- Other hosts can use a separate subagent with the same review protocol.
- When separate review is unavailable, the independent review status remains `PENDING`.
- Native documents require access through the selected editor or provider API.
- Cloud document access can require connector authentication and network access.

## Non-negotiable principle
Treat the existing document as an artifact with accumulated requirements. An editing instruction authorizes only the requested changes. Never silently remove, invert, qualify, embellish, or reinterpret previously established meaning. A fluent rewritten document is not evidence of preservation.

## Inputs and baselines
1. Locate and read the **whole relevant document**, including tables, references, footnotes, captions, embedded text, and appendices. Do not infer unseen content. Where the document is native to Word, Docs, Pages, or another editor, edit through its native operations when available; a Markdown export is an analysis snapshot, not permission to discard formatting or metadata.
2. Obtain the **last approved baseline** (if available) and the **start-of-session snapshot**. They may be identical. Freeze exact copies, record source links/version identifiers and checksums where possible, and never replace them during an editing session.
3. If no approved version can be identified, use the start-of-session snapshot as a *provisional* baseline and report this limitation. Do not invent approval or reconstruct the baseline from memory.
4. For a continuing session, compare each candidate with the start-of-session snapshot **and** the last approved baseline; retain previously accepted changes as explicit, traceable change records.

## Select the workflow
- **Localized**: isolated corrections/additions with bounded scope. Identify touched units; edit in place or propose a small patch; compare changed units and ensure untouched surrounding units are unchanged. Extract explicit invariants only for affected material.
- **Substantial**: multi-section edits, reorganization, synthesis, simplification, or any request to rewrite the whole document. Use the full workflow below, even if the user's instruction is short.
- Escalate a localized edit to substantial if it affects shared definitions, numeric claims, conclusions, citations, dependencies, or multiple sections.

## Full workflow (substantial edits)
1. **Inventory**: Identify all document sections and substantive units. Establish stable IDs for atomic claims, facts, dates, numbers, assumptions, decisions, rationales, constraints, exceptions, references, and actionable requirements. Preserve qualifiers and uncertainty. Include material appearing in tables, appendices, and captions. Create a fact-and-decision ledger following `references/ledger-and-review.md` and `assets/ledger.example.json` (schema example). Record source quotes/anchors for every high-priority item. Exclude unsupported inferences.
2. **Authorize**: Translate the user's request into a change plan (`assets/change-plan.template.md`). Specify allowed changes, affected locations, explicitly protected content, and success criteria. Default everything else to preserved. An instruction to "rewrite" permits new prose and organization, not silent changes of facts or decisions.
3. **Plan the mapping**: For every substantive source unit identify its destination in the proposed structure or an explicit authorized deletion/change ID. If a source unit is merged, enumerate which claims its destination must retain. Plan citation moves and table transformations. Identify dependency and contradiction risks.
4. **Edit**: Prefer precise patches, moves, or scoped replacements in the original document. For broad refactors, construct the new draft while retaining a source-to-destination mapping. Preserve unrequested material verbatim where possible. Avoid converting a rich-text source through lossy exports merely to make editing convenient. Keep candidate separate until checks complete.
5. **Mechanical check**: Compare baseline, session snapshot, and candidate. Where files are plain text/Markdown, use `scripts/check_revision.py`; otherwise use native revision history, tracked changes, document comparison, or provider-specific APIs. Check protected text/sections, amounts, dates, proper names, links, citations, headings, headings with same names, and unexplained edits. Record all differences, not merely a pass/fail.
6. **Independent semantic regression review**: For every substantial revision, delegate the check to a **fresh, separate subagent** after editing, never to the editing agent. In Codex, use the `whip_reviewer` custom agent bundled at `codex/agents/whip_reviewer.toml` after installing it in `.codex/agents/` or `~/.codex/agents/`. Give the reviewer direct access to both immutable baselines, full candidate, change plan, ledger, mapping, and mechanical report. The reviewer must reconstruct baseline claims *independently* to find items omitted by the editor’s ledger, then evaluate each ledger item against candidate evidence. Report: `preserved`, `moved`, `rephrased-equivalent`, `authorized-change`, `missing`, `contradicted`, or `uncertain`. Quote source and candidate spans/locations. Verify exceptions, uncertainty, causal logic, conditional claims, and citation support; don't let a keyword match count as semantic verification. Independently review unexpected new claims and contradictions. Require an evidence-backed JSON reviewer report, covering all ledger IDs, untracked baseline claims, new claims, citations, and mechanical warnings. Wait for its result. Consult `references/reviewer-protocol.md` and `references/ledger-and-review.md`. **If a separate subagent cannot be spawned, mark independent semantic review PENDING; never relabel a self-review as independent.**
7. **Repair and retest**: Repair all unauthorized omissions, contradictions, and unrequested edits in the *parent editing agent*, not in the reviewer. After any candidate change, generate an updated mechanical report and ask the reviewer to independently review the updated candidate. Recheck dependent statements. For semantic uncertainty, report it for human judgment; do not mark as passed by assumption.
8. **Accept**: Only promote a candidate after the mechanical gate passes, the independent reviewer reports PASS with verified evidence, and the release-gate checker passes where applicable. Inspect and adjudicate warnings. Preserve the last approved snapshot and audit trail. If review is unavailable or acceptance is blocked, deliver a candidate and exceptions report without claiming semantic verification.

## Output contract
For localized edits: give the revised passage/document and a short touched/untouched summary.

For substantial edits, deliver or save:
- Revised **candidate** and a comparison/revision artifact, keeping source version intact until validated.
- Ledger with IDs and source anchors; approved and session baselines/version IDs.
- Authorized-change plan and source-to-destination mapping.
- Independent reviewer report (`reviewer-report.json`) with evidence and counts by status, all critical exceptions, unmapped baseline claims, unsupported new claims, numeric/citation diffs, and explicit residual uncertainties.
- Release-gate result (`release-gate.json`) when Markdown/plain text checks apply.
- Clear status: **approved/verified**, **candidate pending review**, or **blocked**. A script's mechanical pass by itself is **not** semantic approval.

## Tooling
For Markdown/plain text, the included deterministic checker is:

```bash
uv run --script scripts/check_revision.py --approved approved.md --session session.md --candidate candidate.md --ledger ledger.json --report regression-report.json
```

The `ledger.json` uses the example in `assets/ledger.example.json`. Optional SHA-256 fields pin the baselines. The checker validates exact protected Markdown sections and required literals, flags numerical drift, and emits JSON. It **cannot** establish semantic equivalence or citation accuracy.

### Independent review subagent

- Install the included Codex custom-agent TOML file from `codex/agents/whip_reviewer.toml` to the project `.codex/agents/` folder (or `~/.codex/agents/` globally), then invoke `whip_reviewer`. The shared Smith installer installs this file with the skill. A standalone skill or plugin installation requires this copy step. See `references/reviewer-protocol.md` for complete invocation and schema.
- The parent writes `reviewer-report.json` from the separate agent's JSON response and validates it. Reviewer instructions are read-only; the parent owns edits. Do not pass only the editor's summary.

```bash
uv run --script scripts/gate_review.py --ledger ledger.json --mechanical mechanical-report.json \
  --review reviewer-report.json --approved approved.md --session session.md \
  --candidate candidate.md --report release-gate.json
```

The gate checks the reviewer report's structure, evidence locations, completeness, and baseline identity but **cannot** independently certify logical equivalence. If no subagents are supported, leave the semantic gate PENDING and report this limitation.

## Boundaries
- The user's current, explicit instruction takes priority over this default preservation policy; record all intentionally changed invariants in the change plan.
- Do not silently overwrite another user's changes or accept conflicting versions; check live version identity before writing.
- If the baseline is inaccessible, source content is incomplete, or preservation cannot be verified, report what cannot be validated. Never manufacture a successful regression result.
- Avoid filling the ledger with tautologies or prose-style preferences unless the user specified them. Concentrate review effort on material meaning.
