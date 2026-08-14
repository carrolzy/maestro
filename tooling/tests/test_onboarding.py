import json
import tempfile
import unittest
from pathlib import Path

from business_card import (
    BUSINESS_CARD_SCHEMA,
    card_to_markdown,
    generate_empty_card,
    load_and_validate_card,
    validate_business_card,
)
from jsonschema_mini import is_valid
from onboard_project import onboard_project
from playbook_schema import PLAYBOOK_SCHEMA, load_and_validate_playbook, validate_playbook
from project_types import list_project_types, project_type_exists, project_type_names
from register_project import register_project
from validate_project import validate_project


def _seed_templates(root: Path) -> None:
    templates = root / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for name in ("business-context", "project-override", "task-context", "project-baseline"):
        (templates / f"{name}.md").write_text(f"# {name}\n\n## Section\n\nplaceholder\n", encoding="utf-8")


def _seed_project_types(root: Path) -> None:
    pt = root / "project-types" / "uniapp-mini-program"
    pt.mkdir(parents=True, exist_ok=True)
    (pt / "README.md").write_text(
        "# Uniapp Mini-Program\n\n## Type Definition\n\nA mini-program template.\n\n## Inspect First\n\n- pages.json\n",
        encoding="utf-8",
    )
    (pt / "rules.md").write_text("1. Check platform restrictions.\n2. Reuse shared components.\n", encoding="utf-8")
    (pt / "pitfalls.md").write_text("- Watch cross-platform regressions.\n", encoding="utf-8")


# ── playbook schema ──────────────────────────────────────────────────


class PlaybookSchemaTests(unittest.TestCase):
    def test_example_wxapp_playbook_validates(self) -> None:
        path = Path(__file__).resolve().parents[2] / "projects" / "example-wxapp" / "playbook.json"
        playbook = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_playbook(playbook)
        self.assertEqual(errors, [], msg=f"example-wxapp playbook should validate: {errors}")

    def test_empty_playbook_validates(self) -> None:
        errors = validate_playbook({"guidance": []})
        self.assertEqual(errors, [])

    def test_playbook_with_project_type_validates(self) -> None:
        errors = validate_playbook({"project_type": "uniapp-mini-program", "guidance": []})
        self.assertEqual(errors, [])

    def test_guidance_entry_with_extra_field_caught(self) -> None:
        errors = validate_playbook(
            {"guidance": [{"keywords": ["cart"], "bogus_field": 1}]}
        )
        self.assertNotEqual(errors, [])

    def test_guidance_entry_missing_keywords_is_invalid(self) -> None:
        errors = validate_playbook({"guidance": [{"risk_flags": []}]})
        self.assertTrue(any("required" in e.lower() for e in errors), msg=errors)

    def test_extra_properties_are_caught_by_additional_properties(self) -> None:
        errors = validate_playbook({"guidance": [], "bogus": 1})
        self.assertNotEqual(errors, [])

    def test_file_not_found_returns_error(self) -> None:
        _, errors = load_and_validate_playbook(Path("/no/such/playbook.json"))
        self.assertTrue(errors)

    def test_bad_json_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "playbook.json"
            path.write_text("not json", encoding="utf-8")
            _, errors = load_and_validate_playbook(path)
            self.assertTrue(errors)


# ── business card schema ─────────────────────────────────────────────


class BusinessCardSchemaTests(unittest.TestCase):
    def test_valid_card_passes(self) -> None:
        card = {
            "project": "test",
            "one_liner": "A test project.",
            "business_goals": ["Goal 1"],
            "user_roles": [],
            "core_business_objects": [],
            "key_business_flows": [],
            "page_or_module_mapping": [],
            "critical_rules": [],
            "interface_semantics": [],
            "historical_pitfalls": [],
        }
        self.assertTrue(is_valid(card, BUSINESS_CARD_SCHEMA))

    def test_missing_one_liner_is_invalid(self) -> None:
        card = {"project": "test"}
        errors = validate_business_card(card)
        self.assertNotEqual(errors, [])

    def test_extra_field_is_invalid(self) -> None:
        card = generate_empty_card("test")
        card["extra"] = 1
        errors = validate_business_card(card)
        self.assertNotEqual(errors, [])

    def test_generate_empty_card_is_valid(self) -> None:
        card = generate_empty_card("my-project", "uniapp-mini-program")
        card["one_liner"] = "filled"
        errors = validate_business_card(card)
        self.assertEqual(errors, [])

    def test_card_to_markdown_includes_all_sections(self) -> None:
        card = generate_empty_card("test")
        card["one_liner"] = "A one-liner."
        md = card_to_markdown(card)
        self.assertIn("# Business Context", md)
        self.assertIn("## Project in One Sentence", md)
        self.assertIn("A one-liner.", md)
        self.assertIn("## Business Goals", md)
        self.assertIn("## Historical Pitfalls", md)

    def test_card_to_markdown_renders_list_items(self) -> None:
        card = generate_empty_card("test")
        card["one_liner"] = "x"
        card["business_goals"] = ["Increase revenue", "Reduce churn"]
        md = card_to_markdown(card)
        self.assertIn("- Increase revenue", md)
        self.assertIn("- Reduce churn", md)

    def test_file_not_found_returns_error(self) -> None:
        _, errors = load_and_validate_card(Path("/no/such/card.json"))
        self.assertTrue(errors)

    def test_bad_json_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.json"
            path.write_text("{bad", encoding="utf-8")
            _, errors = load_and_validate_card(path)
            self.assertTrue(errors)


# ── project types ────────────────────────────────────────────────────


class ProjectTypeDiscoveryTests(unittest.TestCase):
    def test_lists_known_project_types(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        types = list_project_types(system_root)
        names = [t["name"] for t in types]
        self.assertIn("uniapp-mini-program", names)
        self.assertIn("chrome-extension", names)

    def test_every_type_has_description(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        for t in list_project_types(system_root):
            with self.subTest(name=t["name"]):
                self.assertTrue(t["description"], f"{t['name']} should have a description")

    def test_project_type_names_returns_names(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        self.assertEqual(
            project_type_names(system_root),
            [t["name"] for t in list_project_types(system_root)],
        )

    def test_project_type_exists(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        self.assertTrue(project_type_exists("uniapp-mini-program", system_root))
        self.assertFalse(project_type_exists("no-such-type", system_root))

    def test_empty_for_nonexistent_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_project_types(Path(tmp)), [])


# ── validate project ─────────────────────────────────────────────────


class ValidateProjectTests(unittest.TestCase):
    def test_fresh_registered_project_reports_canonical_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            register_project(system_root=root, project="alpha", summary="Alpha.")
            report = validate_project(system_root=root, project="alpha")
            self.assertEqual(report["checks"]["canonical_files"], "ok")

    def test_missing_project_reports_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = validate_project(system_root=Path(tmp), project="ghost")
            self.assertFalse(report["valid"])

    def test_project_without_playbook_warns_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            register_project(system_root=root, project="beta", summary="Beta.")
            report = validate_project(system_root=root, project="beta")
            self.assertEqual(report["checks"]["playbook"], "missing")

    def test_project_with_invalid_playbook_reports_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            register_project(system_root=root, project="gamma", summary="Gamma.")
            (root / "projects" / "gamma" / "playbook.json").write_text(
                json.dumps({"bogus": True}), encoding="utf-8",
            )
            report = validate_project(system_root=root, project="gamma")
            self.assertTrue(report["checks"]["playbook"].startswith("invalid"))

    def test_project_with_valid_playbook_and_card_all_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            register_project(system_root=root, project="delta", summary="Delta.")
            playbook = {"project_type": "uniapp-mini-program", "guidance": []}
            (root / "projects" / "delta" / "playbook.json").write_text(
                json.dumps(playbook), encoding="utf-8",
            )
            card = generate_empty_card("delta", "uniapp-mini-program")
            card["one_liner"] = "A delta project."
            (root / "projects" / "delta" / "business-card.json").write_text(
                json.dumps(card), encoding="utf-8",
            )
            report = validate_project(system_root=root, project="delta")
            self.assertTrue(report["valid"], msg=f"should be valid: {report['issues']}")
            self.assertEqual(report["checks"]["canonical_files"], "ok")
            self.assertEqual(report["checks"]["playbook"], "ok")
            self.assertEqual(report["checks"]["business_card"], "ok")
            self.assertEqual(report["checks"]["project_type_known"], "ok")


# ── onboard project ──────────────────────────────────────────────────


class OnboardProjectTests(unittest.TestCase):
    def test_onboard_creates_all_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            report = onboard_project(
                system_root=root,
                project="epsilon",
                summary="Epsilon project for testing.",
                project_type="uniapp-mini-program",
            )
            project_dir = root / "projects" / "epsilon"
            self.assertTrue((project_dir / "business-context.md").exists())
            self.assertTrue((project_dir / "project-override.md").exists())
            self.assertTrue((project_dir / "task-context.md").exists())
            self.assertTrue((project_dir / "spec" / "project-baseline.md").exists())
            self.assertTrue((project_dir / "playbook.json").exists())
            self.assertTrue((project_dir / "business-card.json").exists())
            self.assertTrue(report["valid"])

    def test_onboarded_playbook_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            onboard_project(
                system_root=root,
                project="zeta",
                summary="Zeta.",
                project_type="uniapp-mini-program",
            )
            playbook_path = root / "projects" / "zeta" / "playbook.json"
            _, errors = load_and_validate_playbook(playbook_path)
            self.assertEqual(errors, [])

    def test_onboarded_card_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            onboard_project(
                system_root=root,
                project="eta",
                summary="Eta.",
                project_type="uniapp-mini-program",
            )
            card_path = root / "projects" / "eta" / "business-card.json"
            _, errors = load_and_validate_card(card_path)
            self.assertEqual(errors, [])

    def test_onboard_without_project_type_still_creates_valid_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_templates(root)
            _seed_project_types(root)
            report = onboard_project(
                system_root=root,
                project="theta",
                summary="Theta.",
            )
            project_dir = root / "projects" / "theta"
            self.assertTrue(project_dir.exists())
            # without playbook or card the report won't be fully valid,
            # but only because those files are opt-in warnings
            self.assertIn("playbook", report["checks"])


if __name__ == "__main__":
    unittest.main()
