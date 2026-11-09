"""Setup dispatch preserves the user's files and delegates config to its owner."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipIf(os.geteuid() == 0, "user setup deliberately refuses root")
class SetupAgentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory setup ")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = os.environ | {"HOME": str(self.home),
                                 "XDG_STATE_HOME": str(self.home / "state"),
                                 "XDG_CONFIG_HOME": str(self.home / "config")}

    def run_setup(self, *args):
        return subprocess.run([str(ROOT / "setup-agent.sh"), *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_config_is_applied_by_the_selected_checkout_including_old_revisions(self):
        for name in ("apply.sh", "setup-agent.sh"):
            checkout = self.home / name.replace(".sh", " checkout")
            checkout.mkdir()
            (checkout / name).write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$HOME/applied"\n')
            result = self.run_setup("apply-dotfiles", str(checkout))
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "applied").read_text(), "apply\nplugins\napply\nplugins\n")

    def test_apply_failure_stops_before_preparing_plugins(self):
        checkout = self.home / "custom dotfiles"
        checkout.mkdir()
        (checkout / "apply.sh").write_text('''#!/bin/sh
if [ "$1" = apply ]; then exit 23; fi
touch "$HOME/unexpected-plugin-install"
''')
        self.assertEqual(self.run_setup("apply-dotfiles", str(checkout)).returncode, 23)
        self.assertFalse((self.home / "unexpected-plugin-install").exists())

    def test_client_migration_preserves_previous_symlink_and_is_idempotent(self):
        client = self.home / ".local/bin/agent-env"
        client.parent.mkdir(parents=True)
        original = self.home / "old checkout/scripts/agent-env.py"
        client.symlink_to(original)
        self.assertNotEqual(self.run_setup("install-client").returncode, 0)
        self.assertEqual(client.readlink(), original)
        result = self.run_setup("install-client", "--replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(client.resolve(), ROOT / "scripts/agent-env.py")
        backups = list((self.home / "state/factory/backups").glob("*/agent-env"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].readlink(), original)
        self.assertEqual(self.run_setup("install-client").returncode, 0)
        self.assertFalse((self.home / "config").exists())

    def test_client_migration_preserves_unrelated_real_file(self):
        client = self.home / ".local/bin/agent-env"
        client.parent.mkdir(parents=True)
        client.write_text("user command\n")
        self.assertNotEqual(self.run_setup("install-client", "--replace").returncode, 0)
        self.assertEqual(client.read_text(), "user command\n")


if __name__ == "__main__":
    unittest.main()
