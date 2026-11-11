"""Preview URL boundaries and preservation of global agent instructions."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


preview = module("previews", ROOT / "plugins/previews/preview.py")
installer = module("install_previews", ROOT / "scripts/install-previews.py")


class PreviewTest(unittest.TestCase):
    def test_only_loopback_web_urls_reach_the_ssh_transport(self):
        for url in [
            "file:///tmp/page.html",
            "http://example.org:3000/",
            "http://user:password@localhost:3000/",
            "http://localhost:22/",
            "http://localhost:65536/",
            "http://localhost:3000/\nOPEN 9999",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                preview.validate_url(url)
        url = "http://localhost:5173/report.html?name=a%20b#result"
        self.assertEqual(preview.validate_url(url).geturl(), url)

    def test_missing_client_reports_failure_instead_of_an_unreachable_link(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with (
            patch.object(preview, "urlopen", return_value=Response()),
            patch.object(preview, "backend", return_value='{"sessions":[]}') as backend,
            self.assertRaisesRegex(RuntimeError, "No preview client connected"),
        ):
            preview.register("http://localhost:5173/")
        self.assertEqual(backend.call_count, 1)

    def test_guidance_is_idempotent_and_preserves_personal_instructions(self):
        original = "Personal preferences stay here.\n"
        once = installer.guidance_content(original, "Use the preview skill.")
        self.assertEqual(
            installer.guidance_content(once, "Use the preview skill."), once
        )
        updated = installer.guidance_content(once, "Updated preview pointer.")
        self.assertTrue(updated.startswith(original))
        self.assertNotIn("Use the preview skill.", updated)
        self.assertIn("Updated preview pointer.", updated)
        for malformed in [
            "<!-- factory:previews -->",
            "<!-- /factory:previews -->",
            once + once,
        ]:
            with self.assertRaises(RuntimeError):
                installer.guidance_content(malformed, "replacement")

    def test_install_preserves_active_overrides_and_tracks_owned_links(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            environment = os.environ | {
                "HOME": str(home),
                "XDG_DATA_HOME": str(home / "data"),
                "XDG_STATE_HOME": str(home / "state"),
                "CODEX_HOME": str(home / "codex"),
                "PI_CODING_AGENT_DIR": str(home / "pi"),
            }
            version = json.loads((ROOT / "plugins/previews/backend.json").read_text())[
                "version"
            ]
            binary = home / "data/factory/preview-backend" / version / "forward"
            binary.parent.mkdir(parents=True)
            binary.write_text("fixture: download already installed")
            for target in [home / "codex/AGENTS.override.md", home / "pi/CLAUDE.md"]:
                target.parent.mkdir(parents=True)
                target.write_text("Preserve these existing instructions.\n")
            with (
                patch.dict(os.environ, environment),
                patch.object(installer.subprocess, "run"),
            ):
                installer.install()
                installer.install()
                self.assertEqual(
                    (home / ".local/bin/factory-preview").resolve(),
                    ROOT / "plugins/previews/preview.py",
                )
                self.assertEqual(
                    (home / ".agents/skills/browser-preview").resolve(),
                    ROOT / "skills/browser-preview",
                )
                self.assertFalse((home / "codex/AGENTS.md").exists())
                self.assertFalse((home / "pi/AGENTS.md").exists())
                for target in [
                    home / "codex/AGENTS.override.md",
                    home / "pi/CLAUDE.md",
                ]:
                    content = target.read_text()
                    self.assertTrue(
                        content.startswith("Preserve these existing instructions.\n")
                    )
                    self.assertEqual(content.count(installer.START), 1)
                backups = list(
                    (home / "state/factory/backups").glob("*/codex-instructions.md")
                )
                self.assertEqual(len(backups), 1)
                self.assertEqual(
                    backups[0].read_text(), "Preserve these existing instructions.\n"
                )
                # An unrelated replacement is never overwritten by reinstall.
                command = home / ".local/bin/factory-preview"
                command.unlink()
                command.write_text("unrelated command")
                with self.assertRaises(RuntimeError):
                    installer.install()
                self.assertEqual(command.read_text(), "unrelated command")


if __name__ == "__main__":
    unittest.main()
