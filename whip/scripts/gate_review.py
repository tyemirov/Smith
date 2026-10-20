#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Fail-closed release gate for an independently reviewed Markdown revision.

Validates report structure, completeness, baseline fingerprints and quoted evidence.
It cannot independently judge semantic equivalence. Python 3.10+, standard library.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

from check_revision import hash_text


ACCEPTED_STATUSES = {
    "preserved", "moved", "rephrased-equivalent", "authorized-change",
    "missing", "contradicted", "uncertain",
}
PASS_STATUSES = {"preserved", "moved", "rephrased-equivalent", "authorized-change"}


def run_gate(ledger: Dict[str, Any], mechanical: Dict[str, Any], review: Dict[str, Any],
             approved_text: str, session_text: str, candidate_text: str) -> Dict[str, Any]:
    blockers: List[str] = []

    def block(message: str) -> None:
        blockers.append(message)

    if mechanical.get("mechanical_gate") != "PASS":
        block("Mechanical gate is not PASS")
    if mechanical.get("semantic_gate") not in ("NOT_TESTED", None):
        block("Mechanical report has unexpected semantic gate; separate review is required")
    if review.get("schema_version") != "1.0":
        block("Unsupported review schema version")
    if review.get("review_completed") is not True:
        block("Independent review is incomplete")
    if review.get("verdict") != "PASS":
        block("Reviewer verdict is not PASS")

    baseline_texts = {"approved": approved_text, "session": session_text, "candidate": candidate_text}
    refs = review.get("baseline_refs", {})
    if not isinstance(refs, dict):
        refs = {}
        block("baseline_refs must be an object")
    for name, source_text in baseline_texts.items():
        digest = hash_text(source_text)
        if mechanical.get(f"{name}_sha256") != digest:
            block(f"Mechanical report's {name} fingerprint does not match current file")
        ref = refs.get(name)
        if not isinstance(ref, str) or f"sha256:{digest}" not in ref:
            block(f"Reviewer did not inspect correct {name} fingerprint")

    ledger_ids: List[str] = []
    for invariant in ledger.get("invariants", []):
        if not isinstance(invariant, dict) or not isinstance(invariant.get("id"), str):
            block("Invalid ledger invariant")
            continue
        ledger_ids.append(invariant["id"])
    if len(ledger_ids) != len(set(ledger_ids)):
        block("Duplicate ledger IDs")
    change_ids = {entry.get("id") for entry in ledger.get("authorized_changes", []) if isinstance(entry, dict)}
    authorization_for = {entry.get("id"): entry.get("authorized_change_id") for entry in ledger.get("invariants", []) if isinstance(entry, dict)}

    rows = review.get("ledger_reviews")
    if not isinstance(rows, list):
        rows = []
        block("ledger_reviews must be an array")
    reviewed_ids: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            block("Every ledger review must be an object")
            continue
        review_id = row.get("id")
        if not isinstance(review_id, str) or not review_id:
            block("Review without a valid ledger ID")
            continue
        reviewed_ids.append(review_id)
        status = row.get("status")
        if status not in ACCEPTED_STATUSES:
            block(f"{review_id}: unrecognized review status")
        elif status not in PASS_STATUSES:
            block(f"{review_id}: unresolved {status} item")
        for source_key in ("source_anchor", "source_quote", "reasoning"):
            if not isinstance(row.get(source_key), str) or not row[source_key].strip():
                block(f"{review_id}: missing {source_key}")
        source_quote = row.get("source_quote")
        if isinstance(source_quote, str) and source_quote and source_quote not in approved_text and source_quote not in session_text:
            block(f"{review_id}: cited source quote is absent from both baselines")
        if status == "authorized-change":
            change_id = row.get("authorized_change_id")
            if not change_id or change_id not in change_ids or authorization_for.get(review_id) != change_id:
                block(f"{review_id}: unauthorized or unregistered semantic change")
        else:
            if row.get("authorized_change_id"):
                block(f"{review_id}: unexpected authorized_change_id for unchanged claim")
        if status != "authorized-change" or row.get("candidate_quote") is not None:
            for field in ("candidate_anchor", "candidate_quote"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    block(f"{review_id}: missing {field}")
            candidate_quote = row.get("candidate_quote")
            if isinstance(candidate_quote, str) and candidate_quote and candidate_quote not in candidate_text:
                block(f"{review_id}: cited candidate quote is absent from candidate")

    if len(reviewed_ids) != len(set(reviewed_ids)):
        block("Duplicate ledger review IDs")
    missing_ids = sorted(set(ledger_ids) - set(reviewed_ids))
    extra_ids = sorted(set(reviewed_ids) - set(ledger_ids))
    if missing_ids:
        block(f"Unreviewed ledger IDs: {', '.join(missing_ids)}")
    if extra_ids:
        block(f"Review refers to unknown ledger IDs: {', '.join(extra_ids)}")

    for key in ("unmapped_baseline_units", "unreviewed_new_claims", "citation_issues", "findings", "limitations"):
        items = review.get(key)
        if not isinstance(items, list):
            block(f"{key} must be an array")
        elif items:
            block(f"{key} contains unresolved items ({len(items)})")

    warnings = mechanical.get("warnings", [])
    required_codes = {entry.get("code") for entry in warnings if isinstance(entry, dict)}
    dispositions = review.get("warning_dispositions")
    if not isinstance(dispositions, list):
        dispositions = []
        block("warning_dispositions must be an array")
    justified = set()
    for entry in dispositions:
        if not isinstance(entry, dict) or not isinstance(entry.get("code"), str):
            block("Malformed warning disposition")
            continue
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            block(f"Warning {entry['code']} lacks review rationale")
        justified.add(entry["code"])
    unaddressed = required_codes - justified
    if unaddressed:
        block("Mechanical warnings not dispositioned: " + ", ".join(sorted(unaddressed)))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_gate": "PASS" if not blockers else "FAIL",
        "mechanical_gate": mechanical.get("mechanical_gate", "UNKNOWN"),
        "reviewer_verdict": review.get("verdict", "UNKNOWN"),
        "ledger_items_expected": len(ledger_ids),
        "ledger_items_reviewed": len(reviewed_ids),
        "blockers": blockers,
        "note": "Structural and evidence gate only; human/AI reviewer must still judge semantic meaning.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an independent semantic-review report")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--mechanical", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--approved", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        mechanical = json.loads(args.mechanical.read_text(encoding="utf-8"))
        review = json.loads(args.review.read_text(encoding="utf-8"))
        result = run_gate(
            ledger, mechanical, review,
            args.approved.read_text(encoding="utf-8"),
            args.session.read_text(encoding="utf-8"),
            args.candidate.read_text(encoding="utf-8"),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"GATE ERROR: {error}", file=sys.stderr)
        return 3
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Release gate: {result['release_gate']}; independent reviewer: {result['reviewer_verdict']}")
    for blocker in result["blockers"]:
        print(f"BLOCK: {blocker}")
    return 0 if result["release_gate"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
