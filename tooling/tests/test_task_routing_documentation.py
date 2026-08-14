import unittest
from pathlib import Path


class TaskRoutingDocumentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2]

    def test_readmes_link_task_routing_guide_and_list_route_tool(self) -> None:
        for name in ("README.md", "README.zh-CN.md"):
            with self.subTest(readme=name):
                content = (self.root / name).read_text(encoding="utf-8")
                self.assertIn("docs/task-routing.md", content)
                self.assertIn("`route_task`", content)
                self.assertIn("documentation_impact", content)

    def test_task_routing_guide_documents_tiers_risk_and_rerouting(self) -> None:
        content = (self.root / "docs" / "task-routing.md").read_text(encoding="utf-8")
        for tier in ("L0", "L1", "L2", "L3"):
            self.assertIn(tier, content)
        self.assertIn("风险否决", content)
        self.assertIn("current_tier", content)
        self.assertIn("documentation_impact", content)
        self.assertIn("只升不降", content)

    def test_global_rules_require_routing_and_documentation_closeout(self) -> None:
        content = (self.root / "base" / "global-rules.md").read_text(encoding="utf-8")
        self.assertIn("task-routing", content)
        self.assertIn("documentation_impact", content)
        self.assertIn("L0", content)
        self.assertIn("L3", content)


if __name__ == "__main__":
    unittest.main()
