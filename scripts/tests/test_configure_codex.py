"""Updating agent defaults preserves unrelated user configuration and auth."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "configure-codex.py"


class ConfigureCodexTest(unittest.TestCase):
    def test_preserves_custom_settings_hook_trust_and_auth_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / "config.toml"
            config.write_text('''model = "previous-model"
model_reasoning_effort = "low"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
# Keep the user's other preferences.
model_verbosity = "low"
[features]
hooks = true
[projects."/home/dev/project"]
trust_level = "trusted"
[hooks.example]
trusted = true
''')
            auth = home / "auth.json"
            auth.write_text('{"test_fixture": true}\n')
            before = tomllib.loads(config.read_text())
            env = os.environ | {"CODEX_HOME": directory, "XDG_STATE_HOME": str(home / "state")}
            subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, capture_output=True)
            updated = config.read_text()
            after = tomllib.loads(updated)
            self.assertEqual(after["model"], "gpt-6.1-sol")
            self.assertEqual(after["model_reasoning_effort"], "high")
            for key in ("model_verbosity", "features", "projects", "hooks"):
                self.assertEqual(after[key], before[key])
            self.assertIn("# Keep the user's other preferences.", updated)
            self.assertEqual(auth.read_text(), '{"test_fixture": true}\n')
            backups = list((home / "state/factory/backups").glob("*/config.toml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(tomllib.loads(backups[0].read_text()), before)
            subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, capture_output=True)
            self.assertEqual(config.read_text(), updated)
            self.assertEqual(list((home / "state/factory/backups").glob("*/config.toml")), backups)


if __name__ == "__main__":
    unittest.main()
