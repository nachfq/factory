#!/usr/bin/env bash
# Run on the Incus host, or stream over SSH. Never publish a logged-in environment.
set -euo pipefail
revision=${1:?Pass the dotfiles Git commit to build}
factory_revision=${2:?Pass the Factory Git commit containing this recipe}
dotfiles_repo=${3:-https://github.com/nachfq/dotfiles.git}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { printf 'Expected a full Git commit.\n' >&2; exit 1; }
[[ "$factory_revision" =~ ^[0-9a-f]{40}$ ]] || { printf 'Expected a full Factory Git commit.\n' >&2; exit 1; }
[[ "$dotfiles_repo" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$ ]] || {
  printf 'Expected a public GitHub HTTPS dotfiles URL without credentials.\n' >&2; exit 1;
}
if [[ $(incus version | sed -n 's/^Server version: //p') == 6.0.0* ]]; then
  printf 'Update Incus to at least 6.0.1 first; 6.0.0 skips dev folders when unpacking published images.\n' >&2
  exit 1
fi
builder="agent-image-build-$(date +%Y%m%d%H%M%S)"
alias_name="agent-base-$(date +%Y%m%d)-${revision:0:8}-${factory_revision:0:8}"
incus launch images:ubuntu/24.04 "$builder" -p agent-pilot -c security.nesting=true \
  -c user.agent-image-builder=true </dev/null
printf 'Building %s from dotfiles %s\n' "$builder" "$revision"
# Keep a failed builder for diagnosis. It never receives credentials or project files.
trap 'printf "Build stopped. Inspect builder: %s\n" "$builder" >&2' ERR
incus exec "$builder" -- env DEBIAN_FRONTEND=noninteractive \
  DOTFILES_REPO="$dotfiles_repo" DOTFILES_REVISION="$revision" FACTORY_REVISION="$factory_revision" \
  bash -s <<'ROOT'
set -euo pipefail
touch /etc/agent-base-builder
id dev >/dev/null 2>&1 || useradd --create-home --uid 1001 --user-group --shell /bin/bash dev
apt-get update -qq
apt-get install -y -qq --no-install-recommends git curl ca-certificates
runuser -u dev -- env GIT_TERMINAL_PROMPT=0 git clone "$DOTFILES_REPO" /home/dev/dotfiles
runuser -u dev -- git -C /home/dev/dotfiles checkout -B main "$DOTFILES_REVISION"
runuser -u dev -- env GIT_TERMINAL_PROMPT=0 git clone https://github.com/nachfq/factory.git /home/dev/factory
runuser -u dev -- git -C /home/dev/factory checkout -B main "$FACTORY_REVISION"
ROOT
incus exec "$builder" --disable-stdin -- bash /home/dev/factory/setup-agent.sh install-tools
incus exec "$builder" --disable-stdin -- bash /home/dev/factory/setup-agent.sh grant-sudo
incus exec "$builder" -- runuser -u dev -- env \
  HOME=/home/dev PATH=/home/dev/.local/bin:/home/dev/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin \
  bash -s <<'USER'
set -euo pipefail
cd /home/dev/factory
./setup-agent.sh install-runtimes
./setup-agent.sh install-codex
./setup-agent.sh install-pi
./setup-agent.sh configure-codex
./setup-agent.sh install-herdr
./setup-agent.sh apply-dotfiles /home/dev/dotfiles
./setup-agent.sh install-skills
sudo -n true
export PATH="$HOME/.pi/agent/bin:$PATH"
for tool in git gh codex pi herdr nvim node npm mise uv fzf bat zoxide btop dua rsync pkg-config; do
  command -v "$tool"
done
! command -v rustc
! command -v cargo
USER
incus exec "$builder" -- bash -s <<'ROOT'
set -euo pipefail
cat > /etc/ssh/sshd_config.d/20-agent-access.conf <<'SSH'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers dev
SSH
systemctl enable ssh.service
python3 /home/dev/factory/infra/incus/prepare-agent-image.py
apt-get clean
ROOT
incus stop "$builder" --timeout 30
incus publish "$builder" --alias "$alias_name" --compression gzip \
  "description=Common agent tools; no project, Rust toolchain or credentials" \
  "user.dotfiles.revision=$revision" "user.dotfiles.repository=$dotfiles_repo" \
  "user.factory.revision=$factory_revision"
fingerprint=$(incus image info "$alias_name" | sed -n 's/^Fingerprint: //p')
if incus image alias list --format csv | cut -d, -f1 | grep -qx agent-base; then
  incus image alias delete agent-base
fi
incus image alias create agent-base "$fingerprint"
incus delete "$builder"
trap - ERR
printf 'Ready: agent-base (%s), immutable alias %s\n' "$fingerprint" "$alias_name"
