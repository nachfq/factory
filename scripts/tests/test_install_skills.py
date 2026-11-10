"""Exercise pinned installs, updates and conflict handling against a real local Git upstream."""

import json
import os
from pathlib import Path
import subprocess
import shutil
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
            'CODEX_HOME': str(self.home / 'codex'),
            'PI_CODING_AGENT_DIR': str(self.home / '.pi/agent'),
        }
        (self.home / 'codex').mkdir()
        (self.home / 'gitconfig').write_text(
            f'[url "{self.upstream.as_uri()}"]\n\tinsteadOf = {REPOSITORY}\n')
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        source = self.upstream / 'skills/example'
        source.mkdir(parents=True)
        self.source = source / 'SKILL.md'
        self.source.write_text('First skill version\n')
        internal = self.upstream / 'skills/internal/SKILL.md'
        internal.parent.mkdir()
        internal.write_text('Unpublished skill\n')
        (self.upstream / 'LICENSE').write_text('Test license\n')
        metadata = self.upstream / '.claude-plugin'
        metadata.mkdir()
        (metadata / 'marketplace.json').write_text(json.dumps(dict(
            name='fixture-skills', owner=dict(name='Fixture'),
            plugins=[dict(name='external-test', source='./')])))
        (metadata / 'plugin.json').write_text(json.dumps(dict(
            name='external-test', version='1.0.0', description='Fixture skills',
            skills=['./skills/example'])))
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
        self.assertEqual((self.skills / 'full-agents').resolve(), ROOT / 'skills/full-agents')
        self.assertFalse((self.skills / 'codex-full-agents').is_symlink())
        self.assertEqual((self.home / '.pi/agent/extensions/pi-agent-messaging').resolve(),
                         ROOT / 'extensions/pi-agent-messaging')
        self.assertFalse((self.home / '.pi/agent/settings.json').exists())
        workers = json.loads((self.home / 'config/factory/config.json').read_text())['workers']
        self.assertEqual(Path(workers['worktrees_root']), self.home / 'worktrees')
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
        result = self.install('--dry-run')
        self.assertIn(str(self.skills / 'full-agents'), result.stdout)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.home / '.local').exists())
        self.assertFalse((self.home / '.pi').exists())
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

    def test_pi_extension_conflict_prevents_all_link_changes(self):
        target = self.home / '.pi/agent/extensions/pi-agent-messaging'
        target.mkdir(parents=True)
        (target / 'personal').write_text('Keep me\n')
        self.install('--replace', success=False)
        self.assertEqual((target / 'personal').read_text(), 'Keep me\n')
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.home / 'data').exists())

    def test_pi_agent_dir_override_preserves_settings(self):
        agent = self.home / 'custom Pi agent'
        agent.mkdir()
        settings = agent / 'settings.json'
        original = '{ "defaultModel": "personal", "extensions": ["/personal.js"] }\n'
        settings.write_text(original)
        self.env['PI_CODING_AGENT_DIR'] = str(agent)
        self.install()
        self.assertEqual(settings.read_text(), original)
        self.assertEqual((agent / 'extensions/pi-agent-messaging').resolve(),
                         ROOT / 'extensions/pi-agent-messaging')
        self.assertFalse((self.home / '.pi').exists())

    def test_previous_managed_codex_skill_is_retired_without_removing_unrelated_skills(self):
        self.skills.mkdir(parents=True)
        old = self.skills / 'codex-full-agents'
        old_source = ROOT / 'skills/codex-full-agents'
        old.symlink_to(old_source)
        unrelated = self.skills / 'personal'
        unrelated.symlink_to(self.upstream)
        ledger = self.home / 'state/factory/skills.json'
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({str(old): str(old_source)}))
        self.install()
        self.assertFalse(old.is_symlink())
        self.assertEqual((self.skills / 'full-agents').resolve(), ROOT / 'skills/full-agents')
        self.assertEqual(unrelated.resolve(), self.upstream)

    def test_unpinned_revision_and_escaping_source_path_fail_before_writes(self):
        entry = yaml.safe_load(self.manifest.read_text())
        for invalid in [dict(revision='main'), dict(path='../outside')]:
            changed = json.loads(json.dumps(entry))
            changed['external'][0].update(invalid)
            self.manifest.write_text(yaml.safe_dump(changed))
            self.install(success=False)
            self.assertFalse(self.skills.exists())

    def native_manifest(self, revision, pi_skills=False):
        self.write_manifest(revision)
        manifest = yaml.safe_load(self.manifest.read_text())
        manifest['external'][0].update(kind='codex-plugin', marketplace='fixture-skills', plugin='external-test')
        if pi_skills:
            manifest['external'][0]['pi_skills'] = True
        self.manifest.write_text(yaml.safe_dump(manifest))

    @unittest.skipUnless(shutil.which('codex'), 'native plugin check requires Codex')
    def test_native_plugin_migration_replaces_link_and_updates_same_version_at_new_commit(self):
        self.install()
        self.native_manifest(self.first)
        self.install()
        self.assertFalse((self.skills / 'external-test').is_symlink())
        cache = self.home / 'codex/plugins/cache/fixture-skills/external-test/1.0.0'
        self.assertEqual((cache / 'skills/example/SKILL.md').read_text(), 'First skill version\n')
        self.assertEqual((cache / 'LICENSE').read_text(), 'Test license\n')
        backups = list((self.home / 'state/factory/backups').glob('*'))
        self.install()
        self.assertEqual(list((self.home / 'state/factory/backups').glob('*')), backups)
        self.native_manifest(self.second)
        self.install(success=False)
        self.install('--replace')
        self.assertEqual((cache / 'skills/example/SKILL.md').read_text(), 'Second skill version\n')
        self.write_manifest()
        self.install()
        self.assertFalse(cache.exists())

    @unittest.skipUnless(shutil.which('codex'), 'native plugin check requires Codex')
    def test_pi_published_skills_follow_pin_without_duplicating_codex_skills(self):
        self.native_manifest(self.first, pi_skills=True)
        self.install()
        link = self.home / '.pi/agent/skills/external-test'
        original = link.readlink()
        self.assertEqual({p.name for p in link.iterdir()}, {'example'})
        self.assertEqual((link / 'example/SKILL.md').read_text(), 'First skill version\n')
        self.assertFalse((self.skills / 'external-test').exists())
        cache = self.home / 'codex/plugins/cache/fixture-skills/external-test/1.0.0'
        self.assertTrue((cache / 'skills/example/SKILL.md').is_file())
        self.install()
        self.assertEqual(link.readlink(), original)
        self.assertFalse((self.home / 'state/factory/backups').exists())
        self.native_manifest(self.second, pi_skills=True)
        self.install(success=False)
        self.assertEqual(link.readlink(), original)
        self.install('--replace')
        self.assertEqual((link / 'example/SKILL.md').read_text(), 'Second skill version\n')
        self.assertEqual((original / 'example/SKILL.md').read_text(), 'First skill version\n')
        self.write_manifest()
        self.install()
        self.assertFalse(link.is_symlink())
        self.assertTrue(original.is_dir())

    def test_pi_published_paths_cannot_escape_upstream_skills(self):
        metadata = self.upstream / '.claude-plugin/plugin.json'
        manifest = json.loads(metadata.read_text())
        manifest['skills'] = ['../outside']
        metadata.write_text(json.dumps(manifest))
        self.git('commit', '--quiet', '-am', 'Invalid published path fixture')
        self.native_manifest(self.git('rev-parse', 'HEAD'), pi_skills=True)
        self.install(success=False)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.home / '.pi').exists())

    def test_pi_skill_conflict_fails_before_fetch_and_preserves_personal_files(self):
        self.native_manifest(self.first, pi_skills=True)
        conflict = self.home / '.pi/agent/skills/external-test'
        conflict.mkdir(parents=True)
        (conflict / 'personal').write_text('Keep me\n')
        self.install('--replace', success=False)
        self.assertEqual((conflict / 'personal').read_text(), 'Keep me\n')
        self.assertFalse((self.home / 'data').exists())
        self.assertFalse(self.skills.exists())

    def test_failed_native_install_keeps_previous_skill_link(self):
        self.install()
        previous = (self.skills / 'external-test').readlink()
        self.native_manifest(self.first)
        binary = self.home / 'fake-bin'
        binary.mkdir()
        stub = binary / 'codex'
        stub.write_text('#!/bin/sh\nexit 17\n')
        stub.chmod(0o755)
        self.env['PATH'] = str(binary) + os.pathsep + self.env['PATH']
        self.install(success=False)
        self.assertEqual((self.skills / 'external-test').readlink(), previous)


if __name__ == '__main__':
    unittest.main()
