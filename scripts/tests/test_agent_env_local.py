"""Direct Incus access and independent SSH credentials on the Incus host."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class LocalClientTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='factory local client ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.environment = os.environ | {'HOME': str(self.home), 'AGENT_ENV_HOST': 'local',
                                         'XDG_STATE_HOME': str(self.home/'state')}
        spec = importlib.util.spec_from_file_location('local_agent_env', ROOT/'scripts/agent-env.py')
        self.client = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, self.environment):
            spec.loader.exec_module(self.client)

    def test_local_management_does_not_ssh_back_to_the_host(self):
        with patch.object(self.client, 'run', return_value='[]') as run:
            self.assertEqual(self.client.instances(), [])
        run.assert_called_once_with(['incus', 'list', '--format', 'json'], text=None)

    def test_direct_ssh_config_has_no_jump_and_uses_an_independent_key(self):
        self.client.save_connection('demo', '10.77.0.9', 'ssh-ed25519 test-host-key')
        config = self.client.SSH_CONFIG.read_text()
        self.assertNotIn('ProxyJump', config)
        self.assertIn('IdentityFile ~/.ssh/agent-env_ed25519', config)
        self.assertIn('StrictHostKeyChecking yes', config)
        self.assertIn('HostName 10.77.0.9', config)

    def test_public_key_creation_is_idempotent_and_preserves_the_users_key(self):
        ssh = self.home/'.ssh'
        ssh.mkdir(mode=0o700)
        (ssh/'id_ed25519').write_text('existing unrelated private key')
        key = self.client.public_key()
        first = key.read_text()
        self.assertTrue(first.startswith('ssh-ed25519 '))
        self.assertEqual(self.client.public_key().read_text(), first)
        self.assertEqual((ssh/'agent-env_ed25519').stat().st_mode & 0o777, 0o600)
        self.assertEqual((ssh/'id_ed25519').read_text(), 'existing unrelated private key')

    def test_old_laptop_connections_retain_their_jump_host_and_key(self):
        self.client.STATE.mkdir(parents=True)
        (self.client.STATE/'legacy.json').write_text(json.dumps({
            'target': 'agent-legacy', 'ip': '10.77.0.2', 'host': 'nacho@homelab',
            'host_key': 'ssh-ed25519 existing-key'}))
        self.client.rebuild_connections()
        config = self.client.SSH_CONFIG.read_text()
        self.assertIn('ProxyJump nacho@homelab', config)
        self.assertIn('IdentityFile ~/.ssh/id_ed25519', config)

    def test_list_uses_incus_including_stopped_guests_and_ignores_saved_connections(self):
        binary = self.home/'bin'
        binary.mkdir()
        fixtures = [{'status': 'Stopped' if name == 'stopped-demo' else 'Running',
                     'config': {'user.agent-env': 'true', 'user.agent-env.name': name}}
                    for name in ['running-demo', 'stopped-demo']]
        fixtures.append({'config': {'user.agent-env.name': 'unmanaged'}})
        incus = binary/'incus'
        incus.write_text('#!/bin/sh\nprintf "%s\\n" ' + "'" + json.dumps(fixtures) + "'\n")
        incus.chmod(0o755)
        ssh = binary/'ssh'
        ssh.write_text('#!/bin/sh\nexit 97\n')
        ssh.chmod(0o755)
        self.client.STATE.mkdir(parents=True)
        (self.client.STATE/'ghost.json').write_text('{}')
        result = subprocess.run([str(ROOT/'scripts/agent-env-local.sh'), 'list', '--names'],
                                env=self.environment | {'PATH': str(binary)+os.pathsep+os.environ['PATH']},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['running-demo', 'stopped-demo'])


if __name__ == '__main__':
    unittest.main()
