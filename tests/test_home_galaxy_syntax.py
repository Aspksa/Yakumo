"""Catch home galaxy JavaScript syntax regressions before merging."""
import shutil
import subprocess
import unittest
from pathlib import Path

class HomeGalaxySyntaxTest(unittest.TestCase):
    def test_home_galaxy_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        file = Path(__file__).resolve().parents[1] / "modules" / "brain" / "galaxy.js"
        result = subprocess.run([node, "--check", str(file)],
                                capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

if __name__ == "__main__":
    unittest.main()
