"""Offline regressions: no credentials or network services required."""
import ast
import hashlib
import re
import subprocess
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from qa_test_support import credentials, isolated_url, require_check


class QASafetyTests(unittest.TestCase):
    def test_removed_credential_fingerprints_do_not_reappear(self):
        # One-way fingerprints avoid preserving exposed credentials in the test.
        forbidden = {'069a1b4133864868c3bcd669f9ee912b94e6643d0abf4b702e07538ea441b062', '7ca4f9c411d86a879aef194ead1e4e1fe761071ff29e21364b2f20cd4a9151a3'}
        filenames = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        for filename in filenames:
            path = ROOT / filename
            if not path.is_file():
                continue
            tokens = re.findall(rb"[^\s`\"']+", path.read_bytes())
            self.assertFalse(any(hashlib.sha256(token).hexdigest() in forbidden for token in tokens), filename)

    def test_credentials_require_explicit_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "AURORA_QA_EMAIL"):
                credentials()

    def test_production_and_credential_urls_are_rejected(self):
        for url in ("https://example.org", "http://user:secret@localhost", "ftp://localhost", "http://localhost/?token=x"):
            with self.subTest(url=url), patch.dict(os.environ, {
                "AURORA_QA_ISOLATED": "1", "URL": url,
            }, clear=True):
                with self.assertRaises(RuntimeError):
                    isolated_url("URL")

    def test_requires_isolation_acknowledgement(self):
        with patch.dict(os.environ, {"URL": "http://localhost:8002"}, clear=True):
            with self.assertRaises(RuntimeError):
                isolated_url("URL")

    def test_allows_explicit_local_fixture(self):
        with patch.dict(os.environ, {"AURORA_QA_ISOLATED": "1", "URL": "http://127.0.0.1:8002/"}, clear=True):
            self.assertEqual(isolated_url("URL"), "http://127.0.0.1:8002")

    def test_failed_check_is_recorded_and_raises(self):
        results = {}
        with self.assertRaises(AssertionError):
            require_check(results, "isolation", False)
        self.assertEqual(results, {"isolation": False})

    def test_qa_controls_are_not_silently_optional(self):
        source = (ROOT / "scripts/e2e_full_corporate_acceptance.py").read_text()
        self.assertNotIn("except Exception", source)
        self.assertNotIn("if await ", source)

    def test_no_literal_credentials_in_qa_or_seed(self):
        for filename in ("capture_telemetry_board.py", "e2e_full_corporate_acceptance.py", "verify_roles_security.py"):
            source = (ROOT / "scripts" / filename).read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fill":
                    if node.args and isinstance(node.args[0], ast.Constant) and any(k in str(node.args[0].value) for k in ("password", "email")):
                        self.assertNotIsInstance(node.args[1], ast.Constant, filename)
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if isinstance(key, ast.Constant) and key.value == "password":
                            self.assertNotIsInstance(value, ast.Constant, filename)
        seed = (ROOT / "backend/scripts/seed_two_censopas_users.py").read_text()
        self.assertNotIn('"password":', seed)
        self.assertIn('os.environ.get("AURORA_SEED_PASSWORD", "")', seed)
        tree = ast.parse(seed)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "password" in target.id.lower():
                        self.fail("Seed must not embed a password literal")


if __name__ == "__main__":
    unittest.main()
