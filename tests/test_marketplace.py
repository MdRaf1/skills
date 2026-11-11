"""Check that the Claude Code marketplace manifest matches the skills on disk."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        text = (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        self.manifest = json.loads(text)

    def test_marketplace_metadata(self):
        self.assertEqual(self.manifest["name"], "mdraf1-skills")
        self.assertTrue(self.manifest["owner"]["name"])

    def test_one_plugin_per_skill(self):
        on_disk = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
        plugins = self.manifest["plugins"]
        self.assertEqual({p["name"] for p in plugins}, on_disk)
        self.assertEqual(len(plugins), len(on_disk))
        for plugin in plugins:
            name = plugin["name"]
            self.assertEqual(plugin["source"], "./")
            self.assertIs(plugin["strict"], False)
            self.assertEqual(plugin["skills"], [f"./skills/{name}"])
            self.assertTrue(plugin["description"])
            self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file())
            # The version comes from the root plugin.json, the single source of truth.
            self.assertNotIn("version", plugin)


if __name__ == "__main__":
    unittest.main()
