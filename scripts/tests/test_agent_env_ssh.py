"""Opt-in integration check against the real Incus image and SSH service.

Run on the laptop with AGENT_ENV_INTEGRATION=1 python3 -m unittest discover
-s scripts/tests. Creates and deletes only a uniquely named test environment.
"""

import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid


SCRIPT = Path(__file__).resolve().parents[1] / "agent-env.py"
SPEC = importlib.util.spec_from_file_location("agent_env", SCRIPT)
agent_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_env)


@unittest.skipUnless(os.environ.get("AGENT_ENV_INTEGRATION") == "1",
                     "requires the laptop's Incus homelab access")
class FirstBootSshTest(unittest.TestCase):
    def test_new_recovers_when_first_boot_exhausted_ssh_start_limit(self):
        name = "ssh-check-" + uuid.uuid4().hex[:10]
        instance = agent_env.instance_name(name)
        incus = agent_env.incus
        created = False

        def incus_with_first_boot_failure(*args, **kwargs):
            nonlocal created
            result = incus(*args, **kwargs)
            if args[:1] == ("launch",):
                created = True
                # The image intentionally has no host keys. Make the first-boot
                # failure deterministic before the real new() prepares access.
                incus("exec", instance, "--", "sh", "-ec", '''
                    systemctl stop ssh.socket ssh.service
                    systemctl reset-failed ssh.service ssh.socket
                    test ! -f /etc/ssh/ssh_host_ed25519_key
                    for attempt in 1 2 3 4 5 6; do
                        systemctl start ssh.service >/dev/null 2>&1 || :
                    done
                    journalctl -u ssh.service -b --no-pager |
                        rg -q 'Start request repeated too quickly'
                ''')
            return result

        try:
            # Exercise actual provisioning without adding a test Herdr profile,
            # starting editors/agents, or touching any user's existing workspace.
            with patch.object(agent_env, "incus", incus_with_first_boot_failure), \
                    patch.object(agent_env, "connect") as connect:
                agent_env.create(name, None)
                connect.assert_called_once_with(name)
            incus("exec", instance, "--", "systemctl", "is-active", "--quiet", "ssh.service")
            incus("exec", instance, "--", "/usr/sbin/sshd", "-t")
            self.assertEqual(incus("exec", instance, "--", "cat",
                                   "/home/dev/.ssh/authorized_keys"),
                             (agent_env.SSH_DIR / "id_ed25519.pub").read_text().strip())
            incus("exec", instance, "--", "test", "-d", "/home/dev/" + name)
            config = json.loads(incus("exec", instance, "--", "python3", "-c",
                                     'import json,tomllib; print(json.dumps(tomllib.load('
                                     'open("/home/dev/.codex/config.toml", "rb"))))'))
            self.assertEqual(config["model"], "gpt-6.1-sol")
            self.assertEqual(config["model_reasoning_effort"], "high")
        finally:
            if created:
                item = agent_env.managed(name)
                self.assertEqual(item["name"], instance)
                incus("delete", instance, "--force")


if __name__ == "__main__":
    unittest.main()
