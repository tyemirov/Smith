# Ledger, traceability, and regression-review procedure

## Ledger extraction
For every substantive atomic claim in the last approved baseline, record:

| Column | Purpose |
|---|---|
| ID | Stable ID, e.g. F-013 (fact), D-004 (decision), A-002 (assumption), Q-007 (qualification), C-001 (citation), R-001 (requirement) |
| Kind | fact, decision, assumption, qualification, citation, requirement, argument, process, context |
| Statement | One falsifiable or inspectable assertion, keeping important exceptions |
| Source anchor | File/version, heading, cell/paragraph/footnote reference, and exact source quote |
| Priority | critical / high / normal |
| Expected disposition | preserve / authorized-change / authorized-delete |
| Authorized change ID | A specific change-plan ID, if applicable |
| Candidate evidence | Exact passage / location supporting preservation or change |
| Review status | preserved, moved, rephrased-equivalent, authorized-change, missing, contradicted, uncertain |

Extract factual numbers and units, dates and date scope, party and organization names, definitions, negations, necessary qualifications, cause-effect relationships, conditional clauses, promises, caveats, key recommendations, and references. Do not silently exclude content because it is awkward to represent. Keep relative references ("this year") tied to their original date context.

**Coverage rule:** For a major rewrite, every substantive baseline unit maps to a candidate destination, or to a clearly authorized change or deletion. Multi-claim paragraphs create multiple ledger entries. A relocated claim needs both an original and a candidate anchor. Lack of proof of deletion is not proof of preservation.

## Change plan
Identify an explicit change ID and scope for each proposed alteration. Differentiate style/structure changes from semantic changes; only the latter authorize changing a claim. If instructions conflict with an earlier decision, record the old and new values, the latest user request supporting the revision, and the consequences for dependent statements.

## Reviewer pass
Use a fresh reading of the approved baseline, session start, ledger, authorized change plan, and candidate. For substantial revisions, delegate review to a fresh, separate agent context. In Codex, install and call `whip_reviewer`. The reviewer must independently reconstruct the material baseline inventory before checking ledger entries, exposing gaps in the editor-built ledger. See `references/reviewer-protocol.md` for the subagent contract and release gate. Do not permit the reviewing agent to retroactively broaden authorization to excuse an observed difference.

For each ledger entry:
1. Locate exact candidate evidence and evaluate logical equivalence, including quantifiers, causality, negation, uncertainty, and conditional requirements.
2. Flag silent drops, unsupported facts, changed emphasis that alters interpretation, altered citations, contradicting sections, and unreviewed numeric drift.
3. Mark `uncertain` rather than filling the gap with assumptions.
4. Confirm changes to numbers, citations, charts, references, and tables against the underlying source, not only the prose.

Perform a **reverse review** of newly introduced candidate assertions. Every new material fact or decision must be grounded in provided sources or supported by an explicitly authorized change.

## Release gates
Mechanical gate: no hash mismatches, no changes to exactly protected sections, no required-literal violations. Warnings require disposition, even if ultimately accepted.

Semantic gate: all critical/high-priority invariants have evidence of preservation, equivalence, or authorization. No unresolved critical contradiction or unauthorized deletion. Every substantive source unit accounted for.

A document passing both gates may be promoted, with residual normal-priority uncertainties disclosed. Mark a merely mechanically checked document `candidate pending semantic review`.

## Native editors
When the source is DOCX, Google Docs, or other rich text, preserve the native document and use supported tracked changes/version history. Structured edits and provider-native element IDs are preferable to wholesale document regeneration. Export to Markdown/plain text only for analysis where loss of formatting, tables, metadata, or embedded media is understood and audited. Native tracked changes remain independently valuable; semantic regression review is still required.
