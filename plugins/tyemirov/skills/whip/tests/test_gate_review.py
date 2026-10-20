import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_revision import hash_text, verify
from gate_review import run_gate


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.approved_text = "# Goals\nTarget: $400,000 annually.\n\n# Customers\nInitial customers are enterprise teams.\n"
        self.session_text = self.approved_text
        self.candidate_text = self.approved_text
        self.ledger = {
            "approved_sha256": hash_text(self.approved_text),
            "session_sha256": hash_text(self.session_text),
            "invariants": [
                {"id": "F-001", "required_literals": ["$400,000"]},
                {"id": "D-001", "required_literals": []},
            ],
            "protected_sections": [],
            "authorized_changes": [],
        }
        self.mechanical = verify(self.approved_text, self.session_text, self.candidate_text, self.ledger)
        self.review = {
            "schema_version": "1.0",
            "review_completed": True,
            "verdict": "PASS",
            "baseline_refs": {
                key: f"{key}.md#sha256:{hash_text(value)}"
                for key, value in (
                    ("approved", self.approved_text),
                    ("session", self.session_text),
                    ("candidate", self.candidate_text),
                )
            },
            "ledger_reviews": [
                {"id": "F-001", "status": "preserved", "source_anchor": "# Goals", "source_quote": "$400,000 annually", "candidate_anchor": "# Goals", "candidate_quote": "$400,000 annually", "authorized_change_id": None, "reasoning": "Exact figure retained"},
                {"id": "D-001", "status": "preserved", "source_anchor": "# Customers", "source_quote": "Initial customers are enterprise teams", "candidate_anchor": "# Customers", "candidate_quote": "Initial customers are enterprise teams", "authorized_change_id": None, "reasoning": "Exact customer cohort retained"},
            ],
            "unmapped_baseline_units": [], "unreviewed_new_claims": [], "citation_issues": [], "findings": [], "limitations": [],
            "warning_dispositions": [
                {"code": warning["code"], "reason": "Reviewer examined this warning against the baselines and candidate"}
                for warning in self.mechanical["warnings"]
            ],
        }

    def evaluate(self):
        return run_gate(self.ledger, self.mechanical, self.review, self.approved_text, self.session_text, self.candidate_text)

    def test_valid_review_passes(self):
        self.assertEqual(self.evaluate()["release_gate"], "PASS")

    def test_missing_ledger_review_fails(self):
        self.review["ledger_reviews"].pop()
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_false_quote_fails(self):
        self.review["ledger_reviews"][0]["candidate_quote"] = "Invented evidence"
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_unmapped_claim_fails(self):
        self.review["unmapped_baseline_units"].append({"quote": "An ignored source claim"})
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_regression_fails(self):
        self.review["ledger_reviews"][1]["status"] = "contradicted"
        self.review["verdict"] = "FAIL"
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_stale_candidate_fails(self):
        self.candidate_text += "\nSilent candidate change.\n"
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_unreviewed_mechanical_warning_fails(self):
        self.review["warning_dispositions"] = []
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_authorization_must_be_registered(self):
        self.review["ledger_reviews"][0]["status"] = "authorized-change"
        self.review["ledger_reviews"][0]["authorized_change_id"] = "CH-FAKE"
        self.assertEqual(self.evaluate()["release_gate"], "FAIL")

    def test_authorized_change_succeeds(self):
        self.ledger["authorized_changes"] = [{"id": "CH-001"}]
        self.ledger["invariants"][0]["authorized_change_id"] = "CH-001"
        self.review["ledger_reviews"][0]["status"] = "authorized-change"
        self.review["ledger_reviews"][0]["authorized_change_id"] = "CH-001"
        self.review["ledger_reviews"][0]["candidate_anchor"] = None
        self.review["ledger_reviews"][0]["candidate_quote"] = None
        self.assertEqual(self.evaluate()["release_gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
