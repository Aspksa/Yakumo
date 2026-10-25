"""Catch home galaxy JavaScript syntax regressions before merging."""
import shutil
import subprocess
import unittest
from pathlib import Path

class HomeGalaxySyntaxTest(unittest.TestCase):
    def test_home_galaxy_uses_real_project_layers(self):
        source = (Path(__file__).resolve().parents[1] / "modules" / "brain" / "galaxy.js").read_text(encoding="utf-8")
        for token in (
            "function projectInterior",
            "function drawProjectInterior",
            'sectorId==="memory"',
            'sectorId==="mind"',
            'sectorId==="growth"',
            'sectorId==="improve"',
            'sectorId==="evolution"',
            'd.entities||[]',
            '(d.mind||{}).thoughts',
            '(d.branches||{}).edges',
            'd.improvements||[]',
            'evo.runs||[]',
            'd.code?.map',
        ):
            self.assertIn(token, source)
        self.assertNotIn("PIXI.", source)

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
