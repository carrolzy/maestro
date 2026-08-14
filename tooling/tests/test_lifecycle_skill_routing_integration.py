"""Cross-skill integration contract for proportional lifecycle routing."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_SKILLS = (
    "project-intake",
    "memory-read-first",
    "verification-before-close",
    "writeback-and-sync",
)


class LifecycleSkillRoutingTests(unittest.TestCase):
    def _read_skill(self, name: str) -> str:
        return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_every_lifecycle_skill_defers_to_route_task_tiers(self) -> None:
        for name in LIFECYCLE_SKILLS:
            with self.subTest(skill=name):
                content = self._read_skill(name)
                self.assertIn("route_task", content)
                for tier in ("L0", "L1", "L2", "L3"):
                    self.assertIn(tier, content)

    def test_closeout_requires_explicit_documentation_impact(self) -> None:
        content = self._read_skill("verification-before-close")
        self.assertIn("documentation_impact", content)
        self.assertIn("not_needed", content)
        self.assertIn("L1", content)
        self.assertIn("L3", content)
        self.assertIn("不得关闭", content)

    def test_l0_skips_full_intake_memory_lifecycle_and_writeback(self) -> None:
        expectations = {
            "project-intake": "L0/L1 不运行本 Skill",
            "memory-read-first": "L0 跳过本 Skill",
            "verification-before-close": "L0 不创建生命周期记录",
            "writeback-and-sync": "L0/L1 默认跳过本 Skill",
        }
        for name, expected in expectations.items():
            with self.subTest(skill=name):
                self.assertIn(expected, self._read_skill(name))


if __name__ == "__main__":
    unittest.main()
