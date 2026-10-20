import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_revision import hash_text, verify, find_section  # noqa: E402


class RegressionCheckerTests(unittest.TestCase):
    def setUp(self):
        self.approved = "# Plan\n\n## Goals\nAnnual target: $400,000.\n\n## Architecture\nLegacy architecture.\n"
        self.session = self.approved
        self.candidate = "# Plan\n\n## Goals\nAnnual target: $400,000.\n\n## Architecture\nReorganized architecture.\n"
        self.ledger = {
            "approved_sha256": hash_text(self.approved),
            "session_sha256": hash_text(self.session),
            "invariants": [{
                "id": "F-001", "kind": "fact", "statement": "Annual target",
                "required_literals": ["$400,000"], "authorized_change_id": None,
            }],
            "protected_sections": [{"heading": "## Goals"}],
            "authorized_changes": [{"id": "CH-001", "description": "Reorganize architecture"}],
        }

    def test_safe_architecture_rewrite(self):
        result = verify(self.approved, self.session, self.candidate, self.ledger)
        self.assertEqual(result["mechanical_gate"], "PASS")
        self.assertEqual(result["semantic_gate"], "NOT_TESTED")

    def test_silent_removal_of_fact_fails(self):
        changed = self.candidate.replace("$400,000", "$300,000")
        result = verify(self.approved, self.session, changed, self.ledger)
        found = {entry["code"] for entry in result["blockers"]}
        self.assertIn("REQUIRED_LITERAL_MISSING", found)
        self.assertIn("PROTECTED_SECTION_CHANGED", found)
        self.assertEqual(result["mechanical_gate"], "FAIL")

    def test_baseline_tampering_fails(self):
        self.ledger["session_sha256"] = "0" * 64
        result = verify(self.approved, self.session, self.candidate, self.ledger)
        self.assertIn("BASELINE_HASH_MISMATCH", [entry["code"] for entry in result["blockers"]])

    def test_ambiguous_headings_flagged(self):
        repeated = self.session + "\n## Goals\nSecond entry\n"
        section = find_section(repeated, "## Goals")
        self.assertEqual(section["error"], "ambiguous")

    def test_numbers_are_flagged_even_for_authorized_rewrite(self):
        changed = self.candidate.replace("Reorganized architecture.", "Architecture cost estimate: $500.")
        result = verify(self.approved, self.session, changed, self.ledger)
        self.assertEqual(result["mechanical_gate"], "PASS")
        self.assertIn("NUMERIC_DRIFT", [entry["code"] for entry in result["warnings"]])

    def test_authorized_fact_change_is_warned_not_blocked(self):
        self.ledger["protected_sections"] = []
        self.ledger["invariants"][0]["authorized_change_id"] = "CH-001"
        changed = self.candidate.replace("$400,000", "$500,000")
        result = verify(self.approved, self.session, changed, self.ledger)
        self.assertEqual(result["mechanical_gate"], "PASS")
        self.assertIn("AUTHORIZED_LITERAL_CHANGED", [entry["code"] for entry in result["warnings"]])


if __name__ == "__main__":
    unittest.main()
