#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Mechanical regression checks for Markdown document revisions.

This tool does not certify preservation of meaning. Use a separate semantic review.
Requires Python 3.10+ and only the standard library.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional


HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:[$€£])?-?\d[\d,]*(?:\.\d+)?(?:[%kKmMbB])?(?![A-Za-z0-9])")


def hash_text(source_text: str) -> str:
    return sha256(source_text.encode("utf-8")).hexdigest()


def find_section(source_text: str, heading: str) -> Dict[str, Any]:
    """Return one Markdown section, including nested sections, or an error."""
    all_headings = list(HEADING_PATTERN.finditer(source_text))
    matches = [match for match in all_headings if f"{match.group(1)} {match.group(2).strip()}" == heading.strip()]
    if len(matches) != 1:
        return {"error": "not_found" if not matches else "ambiguous", "count": len(matches)}
    selected = matches[0]
    selected_level = len(selected.group(1))
    following = [match for match in all_headings if match.start() > selected.start() and len(match.group(1)) <= selected_level]
    end_position = following[0].start() if following else len(source_text)
    return {"text": source_text[selected.start():end_position], "offset": selected.start()}


def item(code: str, message: str, **details: Any) -> Dict[str, Any]:
    return {"code": code, "message": message, **details}


def count_numbers(source_text: str) -> Counter:
    return Counter(NUMBER_PATTERN.findall(source_text))


def verify(approved_text: str, session_text: str, candidate_text: str, ledger: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    checks = {"invariants_checked": 0, "protected_sections_checked": 0}

    if not isinstance(ledger, dict):
        raise ValueError("Ledger root must be an object")

    for digest_key, source_text in (("approved_sha256", approved_text), ("session_sha256", session_text)):
        expected_hash = ledger.get(digest_key)
        if expected_hash and hash_text(source_text) != expected_hash:
            blockers.append(item("BASELINE_HASH_MISMATCH", f"{digest_key} does not match immutable baseline", field=digest_key))
        if not expected_hash:
            warnings.append(item("BASELINE_HASH_UNPINNED", f"{digest_key} is empty; baseline identity is not cryptographically pinned", field=digest_key))

    allowed_change_ids = {entry.get("id") for entry in ledger.get("authorized_changes", []) if isinstance(entry, dict)}
    invariant_ids = set()
    for invariant in ledger.get("invariants", []):
        if not isinstance(invariant, dict):
            blockers.append(item("INVALID_LEDGER", "Every invariant must be an object"))
            continue
        invariant_id = invariant.get("id")
        if not isinstance(invariant_id, str) or not invariant_id or invariant_id in invariant_ids:
            blockers.append(item("INVALID_LEDGER", "Invariant IDs must be unique nonempty strings", id=invariant_id))
            continue
        invariant_ids.add(invariant_id)
        checks["invariants_checked"] += 1
        authorized_change_id = invariant.get("authorized_change_id")
        if authorized_change_id and authorized_change_id not in allowed_change_ids:
            blockers.append(item("UNKNOWN_AUTHORIZATION", "Invariant references an unknown authorized change", id=invariant_id, authorized_change_id=authorized_change_id))
            continue
        required_literals = invariant.get("required_literals", [])
        if not isinstance(required_literals, list) or any(not isinstance(literal, str) or not literal for literal in required_literals):
            blockers.append(item("INVALID_LEDGER", "required_literals must be a list of nonempty strings", id=invariant_id))
            continue
        for literal in required_literals:
            if literal not in approved_text and literal not in session_text:
                blockers.append(item("UNSOURCED_LITERAL", "Ledger literal is absent from both baselines", id=invariant_id, literal=literal))
            if authorized_change_id:
                if literal not in candidate_text:
                    warnings.append(item("AUTHORIZED_LITERAL_CHANGED", "An authorized invariant literal changed; verify the replacement semantically", id=invariant_id, literal=literal, authorized_change_id=authorized_change_id))
            elif literal not in candidate_text:
                blockers.append(item("REQUIRED_LITERAL_MISSING", "Required invariant literal disappeared", id=invariant_id, literal=literal))
        for literal in invariant.get("forbidden_literals", []):
            if literal in candidate_text:
                blockers.append(item("FORBIDDEN_LITERAL_PRESENT", "Forbidden literal found in candidate", id=invariant_id, literal=literal))
        if not required_literals:
            warnings.append(item("SEMANTIC_ONLY_INVARIANT", "No mechanical literal checks for this invariant; semantic review required", id=invariant_id))

    seen_protected_sections = set()
    for section in ledger.get("protected_sections", []):
        if not isinstance(section, dict) or not isinstance(section.get("heading"), str):
            blockers.append(item("INVALID_LEDGER", "Each protected section needs a Markdown heading"))
            continue
        heading = section["heading"]
        if heading in seen_protected_sections:
            blockers.append(item("INVALID_LEDGER", "Duplicate protected heading", heading=heading))
            continue
        seen_protected_sections.add(heading)
        checks["protected_sections_checked"] += 1
        original = find_section(session_text, heading)
        updated = find_section(candidate_text, heading)
        if "error" in original:
            blockers.append(item("SESSION_SECTION_UNAVAILABLE", "Protected section missing or ambiguous in session baseline", heading=heading, reason=original["error"]))
        if "error" in updated:
            blockers.append(item("CANDIDATE_SECTION_UNAVAILABLE", "Protected section missing or ambiguous in candidate", heading=heading, reason=updated["error"]))
        if "error" not in original and "error" not in updated and original["text"] != updated["text"]:
            blockers.append(item("PROTECTED_SECTION_CHANGED", "Protected section differs from session baseline", heading=heading))

    session_numbers = count_numbers(session_text)
    candidate_numbers = count_numbers(candidate_text)
    dropped_numbers = list((session_numbers - candidate_numbers).elements())
    introduced_numbers = list((candidate_numbers - session_numbers).elements())
    if dropped_numbers or introduced_numbers:
        warnings.append(item("NUMERIC_DRIFT", "Review every changed number/unit/date, including intended edits", removed=sorted(dropped_numbers), added=sorted(introduced_numbers)))

    warnings.append(item("SEMANTIC_REVIEW_REQUIRED", "Mechanical inspection cannot verify semantic preservation, citations, qualifications, or completeness"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "approved_sha256": hash_text(approved_text),
        "session_sha256": hash_text(session_text),
        "candidate_sha256": hash_text(candidate_text),
        "mechanical_gate": "FAIL" if blockers else "PASS",
        "semantic_gate": "NOT_TESTED",
        "promotion_status": "BLOCKED" if blockers else "CANDIDATE_PENDING_SEMANTIC_REVIEW",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mechanical regression checks; semantic verification still required")
    parser.add_argument("--approved", required=True, type=Path, help="Last approved baseline (immutable)")
    parser.add_argument("--session", required=True, type=Path, help="Start-of-session baseline (immutable)")
    parser.add_argument("--candidate", required=True, type=Path, help="Proposed revision")
    parser.add_argument("--ledger", required=True, type=Path, help="JSON fact and decision ledger")
    parser.add_argument("--report", type=Path, help="Write full JSON report here")
    args = parser.parse_args()
    try:
        approved_text = args.approved.read_text(encoding="utf-8")
        session_text = args.session.read_text(encoding="utf-8")
        candidate_text = args.candidate.read_text(encoding="utf-8")
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        result = verify(approved_text, session_text, candidate_text, ledger)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"CHECK ERROR: {error}", file=sys.stderr)
        return 3
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Mechanical gate: {result['mechanical_gate']}; semantic gate: {result['semantic_gate']}")
    print(f"Invariants: {result['checks']['invariants_checked']}; protected sections: {result['checks']['protected_sections_checked']}")
    for blocker in result["blockers"]:
        print(f"BLOCK: {blocker['code']} - {blocker['message']}")
    for warning in result["warnings"]:
        print(f"WARN: {warning['code']} - {warning['message']}")
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
