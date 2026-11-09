"""Exercise pinned installs, updates and conflict handling against a real local Git upstream."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'https://github.com/example/skills.git'


@unittest.skipIf(os.geteuid() == 0, 'skills are installed as the regular user')
class InstallSkillsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='factory skills ')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.skills = self.home / '.agents/skills'
        self.upstream = self.home / 'upstream'
        self.upstream.mkdir()
        self.env = os.environ | {
            'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / 'config'),
            'XDG_DATA_HOME': str(self.home / 'data'), 'XDG_STATE_HOME': str(self.home / 'state'),
            'GIT_CONFIG_GLOBAL': str(self.home / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1',
        }
        (self.home / 'gitconfig').write_text(
            f'[url "{self.upstream.as_uri()}"]\n\tinsteadOf = {REPOSITORY}\n')
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        source = self.upstream / 'skills/example'
        source.mkdir(parents=True)
        self.source = source / 'SKILL.md'
        self.source.write_text('First skill version\n')
        (self.upstream / 'LICENSE').write_text('Test license\n')
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'First')
        self.first = self.git('rev-parse', 'HEAD')
        self.source.write_text('Second skill version\n')
        self.git('commit', '--quiet', '-am', 'Second')
        self.second = self.git('rev-parse', 'HEAD')
        self.manifest = self.home / 'skills.yaml'
        self.write_manifest(self.first)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.upstream), *args], env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def write_manifest(self, revision=None):
        entries = [] if revision is None else [dict(name='external-test', repository=REPOSITORY,
                                                    revision=revision, path='skills')]
        self.manifest.write_text(yaml.safe_dump(dict(version=1, external=entries)))

    def install(self, *args, success=True):
        result = subprocess.run([str(ROOT / 'setup-agent.sh'), 'install-skills',
                                 '--manifest', str(self.manifest), *args], env=self.env,
                                capture_output=True, text=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_pinned_checkout_keeps_license_and_reinstall_is_idempotent(self):
        self.install()
        link = self.skills / 'external-test'
        original = link.readlink()
        self.assertEqual((link / 'example/SKILL.md').read_text(), 'First skill version\n')
        self.assertEqual((link.resolve().parent / 'LICENSE').read_text(), 'Test license\n')
        self.assertTrue((self.skills / 'herdr-nvim/scripts/show_file.py').is_file())
        workers = json.loads((self.home / 'config/factory/config.json').read_text())['workers']
        self.assertTrue(Path(workers['worktrees_root']).is_dir())
        self.assertTrue(workers['yolo'])
        self.install()
        self.assertEqual(link.readlink(), original)
        self.assertFalse((self.home / 'state/factory/backups').exists())

    def test_update_needs_replace_and_keeps_previous_revision_and_link_backup(self):
        self.install()
        link = self.skills / 'external-test'
        original = link.readlink()
        self.write_manifest(self.second)
        self.install(success=False)
        self.assertEqual(link.readlink(), original)
        self.install('--replace')
        self.assertEqual((link / 'example/SKILL.md').read_text(), 'Second skill version\n')
        self.assertEqual((original / 'example/SKILL.md').read_text(), 'First skill version\n')
        backups = list((self.home / 'state/factory/backups').glob('*/external-test'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].readlink(), original)

    def test_real_directory_conflict_prevents_all_link_changes(self):
        conflict = self.skills / 'herdr-nvim'
        conflict.mkdir(parents=True)
        (conflict / 'mine').write_text('Keep me')
        self.install('--replace', success=False)
        self.assertFalse((self.skills / 'codex-full-agents').exists())
        self.assertFalse((self.home / 'data').exists())
        self.assertEqual((conflict / 'mine').read_text(), 'Keep me')

    def test_dry_run_does_not_write_or_fetch(self):
        self.install('--dry-run')
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.home / 'data').exists())
        self.assertFalse((self.home / 'config').exists())

    def test_blocked_worker_config_parent_does_not_change_links(self):
        config = self.home / 'config'
        config.mkdir()
        (config / 'factory').write_text('Personal file\n')
        self.install(success=False)
        self.assertFalse(self.skills.exists())
        self.assertEqual((config / 'factory').read_text(), 'Personal file\n')

    def test_retirement_only_removes_the_previous_managed_link(self):
        self.install()
        unrelated = self.skills / 'another-skill'
        unrelated.symlink_to(self.upstream)
        self.write_manifest()
        self.install()
        self.assertFalse((self.skills / 'external-test').is_symlink())
        self.assertEqual(unrelated.resolve(), self.upstream)

    def test_edited_external_source_is_preserved_and_not_silently_installed(self):
        self.install()
        source = self.skills / 'external-test/example/SKILL.md'
        source.write_text('Local edit\n')
        self.install(success=False)
        self.assertEqual(source.read_text(), 'Local edit\n')

    def test_worker_preferences_migrate_without_copying_personal_profiles(self):
        previous = self.home / 'config/harness-fq/config.json'
        previous.parent.mkdir(parents=True)
        workers = dict(yolo=False, worktrees_root='/existing/personal/storage')
        previous.write_text(json.dumps(dict(workers=workers, profiles={'private': 'local only'})))
        self.install()
        current = self.home / 'config/factory/config.json'
        self.assertEqual(json.loads(current.read_text()), dict(workers=workers))
        self.assertIn('profiles', json.loads(previous.read_text()))

    def test_unpinned_revision_and_escaping_source_path_fail_before_writes(self):
        entry = yaml.safe_load(self.manifest.read_text())
        for invalid in [dict(revision='main'), dict(path='../outside')]:
            changed = json.loads(json.dumps(entry))
            changed['external'][0].update(invalid)
            self.manifest.write_text(yaml.safe_dump(changed))
            self.install(success=False)
            self.assertFalse(self.skills.exists())


if __name__ == '__main__':
    unittest.main()
