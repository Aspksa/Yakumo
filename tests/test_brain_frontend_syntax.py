"""Regression guard: the Brain frontend must parse before it can register its menu."""
import shutil
import subprocess
import unittest
from pathlib import Path


class BrainJavascriptSyntaxTest(unittest.TestCase):
    def test_brain_script_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        script = Path(__file__).resolve().parents[1] / "modules" / "brain" / "brain.js"
        result = subprocess.run([node, "--check", str(script)],
                                capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
