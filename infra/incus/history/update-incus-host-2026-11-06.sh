#!/usr/bin/env bash
# Historical migration record. Staged packages were removed after installation.
# For a fresh host, follow ../README.md instead.
# Install the already verified 6.0 LTS packages staged on homelab.
set -euo pipefail
(( EUID == 0 )) || { printf 'Run with sudo on homelab.\n' >&2; exit 1; }
package_dir=${1:-/home/nacho/incus-pilot/incus-update}
python3 - "$package_dir" <<'PY'
from pathlib import Path
import hashlib, json, sys
folder = Path(sys.argv[1])
packages = json.loads((folder/'packages.json').read_text())
assert {p['name'] for p in packages} == {'incus', 'incus-base', 'incus-client'}
for package in packages:
    assert package['version'] == '1:6.0.7-ubuntu24.04-202610301755'
    assert Path(package['file']).name == package['file']
    assert hashlib.sha256((folder/package['file']).read_bytes()).hexdigest() == package['sha256']
PY
fingerprint=$(gpg --batch --with-colons --show-keys "$package_dir/zabbly.asc" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')
[[ "$fingerprint" == 4EFC590696CB15B87C73A3AD82CC8797C838DCFD ]]
umask 077
backup="/home/nacho/incus-pilot/backups/incus-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
incus admin sql global .dump > "$backup/database.sql"
incus config show > "$backup/server.yaml"
incus list --format json > "$backup/instances.json"
incus profile list --format json > "$backup/profiles.json"
cp -a /etc/default/incus "$backup/default-incus"
cp -a /etc/systemd/system/incus.service.d "$backup/systemd-overrides"
install -d -m 755 /etc/apt/keyrings
install -m 644 "$package_dir/zabbly.asc" /etc/apt/keyrings/zabbly.asc
cat > /etc/apt/sources.list.d/zabbly-incus-lts-6.0.sources <<'SOURCE'
Enabled: yes
Types: deb
URIs: https://pkgs.zabbly.com/incus/lts-6.0
Suites: noble
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/zabbly.asc
SOURCE
chmod 644 /etc/apt/sources.list.d/zabbly-incus-lts-6.0.sources
apt-get update -qq
DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y \
  --no-install-recommends --no-remove -o Dpkg::Options::=--force-confold "$package_dir/"*.deb
systemctl daemon-reload
systemctl restart incus.service
incus admin waitready --timeout=60
systemctl restart incus-pilot-network.service
incus version
incus list
printf 'Backup: %s\n' "$backup"
curl --fail --silent --show-error --insecure https://100.111.60.36:8443/ui/ -o /dev/null
printf 'Incus 6.0 LTS updated; panel responds.\n'
