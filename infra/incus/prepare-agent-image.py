"""Remove instance identity from the fresh, unauthenticated image builder only."""
from pathlib import Path
import os
import shutil

assert os.geteuid() == 0
marker = Path('/etc/agent-base-builder')
assert marker.exists(), 'Not the fresh image builder'
home = Path('/home/dev')
for forbidden in [home/'.codex/auth.json', home/'.pi/agent/auth.json',
                  home/'.config/gh/hosts.yml', home/'.ssh/authorized_keys']:
    assert not forbidden.exists(), f'Unexpected credential/access file: {forbidden}'
for path in [home/'.cache', Path('/root/.cache'), Path('/var/lib/apt/lists')]:
    if path.exists():
        shutil.rmtree(path)
for path in [home/'.bash_history', Path('/root/.bash_history')]:
    path.unlink(missing_ok=True)
for path in Path('/etc/ssh').glob('ssh_host_*'):
    path.unlink()
Path('/etc/machine-id').write_text('')
Path('/var/lib/dbus/machine-id').unlink(missing_ok=True)
Path('/var/lib/dbus/machine-id').symlink_to('/etc/machine-id')
marker.unlink()
