from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "tools" / "2d-sprite-and-animation" / "index.html"


class SpriteWorkbenchSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_html = INDEX_HTML.read_text(encoding="utf-8")

    def test_main_nav_preserves_room_and_account_controls(self):
        html = self.index_html
        self.assertIn('id="room-creation-link"', html)
        self.assertIn(">Room Creation<", html)
        self.assertIn('aria-label="Account settings"', html)
        self.assertIn('class="btn-nav-account"', html)
        self.assertIn("Account", html)
        self.assertIn(">Sign Out<", html)

    def test_home_view_contains_integrated_product_marketing_sections(self):
        html = self.index_html
        self.assertIn("A focused pipeline for side-view characters.", html)
        self.assertIn("What it gives you", html)
        self.assertIn("One brief to one runtime package.", html)
        self.assertIn(">Chosen look<", html)
        self.assertIn(">Animate<", html)
        self.assertIn("Export that looks like handoff.", html)
        self.assertIn("Who it fits.", html)
        self.assertIn("Local-first by design.", html)

    def test_docs_view_contains_quickstart_and_export_guidance(self):
        html = self.index_html
        self.assertIn("How the workbench is meant to be used.", html)
        self.assertIn('id="quickstart"', html)
        self.assertIn('id="workflow"', html)
        self.assertIn('id="export-format"', html)
        self.assertIn('id="phaser-guide"', html)
        self.assertIn('id="faq"', html)
        self.assertIn("Runtime export", html)
        self.assertIn("Project export", html)
        self.assertIn("Phaser guide", html)

    def test_docs_view_links_to_export_contract_and_phaser_handoff_guides(self):
        html = self.index_html
        self.assertIn("../../docs/sprite-workbench-runtime-export-contract.md", html)
        self.assertIn("Read the full runtime export contract", html)
        self.assertIn("../../docs/sprite-workbench-phaser-handoff.md", html)
        self.assertIn("Read the Phaser handoff guide", html)


if __name__ == "__main__":
    unittest.main()
