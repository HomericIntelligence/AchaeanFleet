"""Source contracts for the native CI toolkit; image execution is separate."""

import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeCIImageContract(unittest.TestCase):
    def test_pixi_supports_both_linux_architectures_without_arm_bats_conda(self):
        manifest = tomllib.loads((ROOT / "pixi.toml").read_text())
        self.assertEqual(set(manifest["workspace"]["platforms"]), {"linux-64", "linux-aarch64"})
        development = manifest["feature"]["dev"]
        self.assertNotIn("bats-core", development.get("dependencies", {}))
        self.assertEqual(development["target"]["linux-64"]["dependencies"]["bats-core"], ">=1.11.0")

    def test_ci_image_checks_every_required_tool(self):
        dockerfile = (ROOT / "ci" / "Containerfile").read_text()
        commands = "\n".join(line for line in dockerfile.replace("\\\n", " ").splitlines()
                             if line.startswith("RUN "))
        for tool in ("pixi", "uv", "node", "npm", "bats", "gitleaks", "trivy",
                     "docker-compose", "nomad", "hadolint", "markdownlint-cli2"):
            with self.subTest(tool=tool):
                self.assertRegex(commands, rf"\b{re.escape(tool)}\s+(?:--version|version)\b")

    def test_markdown_cli_has_an_exact_node22_compatible_pin(self):
        path = ROOT / "ci" / "package.json"
        self.assertTrue(path.is_file(), "The CI image needs its own locked markdown CLI dependency")
        manifest = json.loads(path.read_text())
        self.assertTrue(manifest["private"])
        self.assertEqual(manifest["dependencies"]["markdownlint-cli2"], "0.23.2")
        self.assertEqual(manifest["engines"]["node"], ">=22 <23")


if __name__ == "__main__":
    unittest.main()
