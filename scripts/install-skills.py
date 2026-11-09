#!/usr/bin/env python3
"""Install Factory's own skills and pinned third-party collections for this user."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    sys.exit('Install PyYAML first (Ubuntu: sudo apt-get install python3-yaml).')


ROOT = Path(__file__).resolve().parents[1]


def directory(variable, fallback):
    return Path(os.environ.get(variable) or fallback).expanduser().absolute()


def read_manifest(path):
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Expected skills manifest version: 1')
    entries = data.get('external', [])
    if not isinstance(entries, list):
        raise ValueError('external must be a list')
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Each external skill must be a mapping')
        name = entry.get('name', '')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name) or name in names:
            raise ValueError(f'Invalid or duplicate skill name: {name}')
        names.add(name)
        repository = entry.get('repository', '')
        if not isinstance(repository, str) or not re.fullmatch(
                r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', repository):
            raise ValueError(f'{name}: expected a public GitHub HTTPS repository without credentials')
        revision = entry.get('revision', '')
        if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError(f'{name}: pin revision to a full Git commit')
        raw_path = entry.get('path', '')
        path = PurePosixPath(raw_path) if isinstance(raw_path, str) else PurePosixPath('/')
        if not raw_path or path.is_absolute() or '..' in path.parts:
            raise ValueError(f'{name}: path must stay inside its repository')
    return entries


def git(checkout, *args):
    return subprocess.run(['git', '-C', str(checkout), *args], check=True,
                          capture_output=True, text=True,
                          env=os.environ | {'GIT_TERMINAL_PROMPT': '0'}).stdout.strip()


def checkout_source(entry, sources):
    target = sources / entry['name'] / entry['revision']
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.fetch-', dir=target.parent))
        try:
            git(staging, 'init', '--quiet')
            git(staging, 'remote', 'add', 'origin', entry['repository'])
            git(staging, 'fetch', '--quiet', '--depth=1', 'origin', entry['revision'])
            git(staging, 'checkout', '--quiet', '--detach', 'FETCH_HEAD')
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    if git(target, 'rev-parse', 'HEAD') != entry['revision']:
        raise ValueError(f'Wrong revision in {target}')
    if git(target, 'config', '--get', 'remote.origin.url') != entry['repository']:
        raise ValueError(f'Wrong upstream in {target}')
    if git(target, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError(f'Third-party checkout was edited: {target}; preserve edits before reinstalling')
    source = (target / entry['path']).resolve()
    if not source.is_relative_to(target.resolve()) or not source.is_dir() or not list(source.rglob('SKILL.md')):
        raise ValueError(f'No skills at {entry["name"]}:{entry["path"]}')
    return source


def check_parents(target):
    for parent in target.parents:
        if os.path.lexists(parent) and not parent.is_dir():
            raise ValueError(f'Target parent is not a directory: {parent}')


def preflight(links, replace):
    for target, source in links.items():
        check_parents(target)
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if os.path.lexists(target) and (not target.is_symlink() or not replace):
            raise ValueError(f'Existing skill: {target}; --replace backs up symlinks only')


def prepare_workers(config, data):
    target = config / 'factory/config.json'
    if target.exists():
        return
    legacy = config / 'harness-fq/config.json'
    if legacy.is_file():
        workers = json.loads(legacy.read_text()).get('workers')
    else:
        workers = None
    if not isinstance(workers, dict):
        worktrees = data / 'factory/worktrees'
        worktrees.mkdir(parents=True, exist_ok=True)
        workers = {
            'worktrees_root': str(worktrees),
            'types': {'implementer': {'model': 'gpt-6.1-sol', 'reasoning_effort': 'high'},
                      'reviewer': {'model': 'gpt-6.1-sol', 'reasoning_effort': 'xhigh'}},
            'yolo': True,
            'herdr': {'layout': 'agent-nvim-lazygit'},
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'workers': workers}, indent=2) + '\n')
    print(f'Created worker preferences: {target}')


def install(args):
    entries = read_manifest(args.manifest)
    data = directory('XDG_DATA_HOME', Path.home() / '.local/share')
    state = directory('XDG_STATE_HOME', Path.home() / '.local/state') / 'factory'
    config = directory('XDG_CONFIG_HOME', Path.home() / '.config')
    skills = args.skills_dir.expanduser().absolute()
    sources = data / 'factory/skill-sources'
    links = {skills / p.name: p.resolve() for p in sorted((ROOT / 'skills').iterdir())
             if (p / 'SKILL.md').is_file()}
    for entry in entries:
        target = skills / entry['name']
        if target in links:
            raise ValueError(f'External name conflicts with an own skill: {target.name}')
        source = sources / entry['name'] / entry['revision'] / entry['path']
        links[target] = source
    preflight(links, args.replace)
    for target in [state / 'skills.json', config / 'factory/config.json']:
        check_parents(target)
    if args.dry_run:
        for target, source in links.items():
            print(f'Link {target} -> {source}')
        print('Dry run: no files changed or sources downloaded.')
        return
    for entry in entries:
        links[skills / entry['name']] = checkout_source(entry, sources)
    preflight(links, args.replace)
    ledger = state / 'skills.json'
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    if not isinstance(previous, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in previous.items()):
        raise ValueError(f'Invalid managed skill record: {ledger}')
    # Parse preferences before changing any links, so malformed local JSON fails early.
    for path in [config / 'factory/config.json', config / 'harness-fq/config.json']:
        if path.exists():
            if not isinstance(json.loads(path.read_text()), dict):
                raise ValueError(f'Expected a configuration object: {path}')
    backup = state / 'backups' / ('skills-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    for target, source in links.items():
        if target.is_symlink() and target.resolve() == source:
            continue
        if target.is_symlink():
            backup.mkdir(parents=True, exist_ok=True)
            target.rename(backup / target.name)
            print(f'Backed up {target} under {backup}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)
        print(f'Linked {target} -> {source}')
    for target_name, source_name in previous.items():
        target = Path(target_name)
        if target.parent == skills and target not in links and target.is_symlink() and target.readlink() == Path(source_name):
            target.unlink()
            print(f'Removed retired managed link: {target}')
    prepare_workers(config, data)
    state.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({str(k): str(v) for k, v in links.items()}, indent=2) + '\n')
    print('Installed skill bundle. Skills are available on your next Codex turn.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'skills.yaml')
    parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--replace', action='store_true', help='Back up and replace conflicting symlinks')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.exit(1, 'Run install-skills as the environment user, not root.\n')
    install(args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, yaml.YAMLError, subprocess.SubprocessError) as error:
        sys.exit(f'Skill installation failed: {error}')
