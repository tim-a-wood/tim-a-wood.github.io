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
        self.assertIn("One character, carried cleanly through production.", html)
        self.assertIn("What you keep", html)
        self.assertIn("From brief to runtime package.", html)
        self.assertIn(">Chosen look<", html)
        self.assertIn(">Animate<", html)
        self.assertIn("Exports that already look usable.", html)
        self.assertIn("Where it fits best.", html)
        self.assertIn("Keep the project. Export the game package.", html)

    def test_docs_view_contains_quickstart_and_export_guidance(self):
        html = self.index_html
        self.assertIn("A short guide to the workbench.", html)
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

    def test_sidebar_contains_sample_project_surface_for_no_credit_testing(self):
        html = self.index_html
        self.assertIn('id="sample-project-block"', html)
        self.assertIn(">Sample Project<", html)
        self.assertIn('id="sample-project-card"', html)

    def test_animations_stage_exposes_confirm_and_continue_action(self):
        html = self.index_html
        self.assertIn('id="confirm-animations-step"', html)
        self.assertIn("Confirm &amp; Continue", html)


if __name__ == "__main__":
    unittest.main()
