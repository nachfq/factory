#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

usage() {
  cat <<'HELP'
Usage: ./setup-agent.sh COMMAND [ARGUMENT]

  apply-dotfiles PATH  Apply a dotfiles checkout and restore its editor plugins.
  install-client  Link agent-env and its Bash completion; does not apply configs.
                  Use --replace to back up and replace an older command symlink.
                  Use --local on the Incus host to avoid SSH to itself.
  install-tools  Install development tools and gh on Ubuntu Linux x86_64.
                 Requires root or sudo; does not apply user configuration.
  install-runtimes  Install mise, Node LTS/npm and uv as the regular user.
  grant-sudo     Allow dev to install packages without a password inside Incus.
                 Run as root inside the disposable environment only.
  install-codex  Install/update Codex using the official installer as this user.
  install-pi     Install/update Pi using the official installer as this user.
  configure-codex  Default Codex to GPT-6.1 Sol / high with full access (YOLO).
                   Run only inside the disposable agent environment.
  install-herdr  Install/update Herdr and its Codex status integration as this user.
  install-previews  Install private browser previews for Herdr, Pi and Codex.
  install-skills  Install own skills and the pinned third-party bundle.
                  Use --dry-run to preview, or --replace to back up old symlinks.

Logins and project dependencies are configured separately.
HELP
}

install_tools() {
  # shellcheck source=/dev/null
  . /etc/os-release
  if [[ "$ID" != ubuntu || $(uname -m) != x86_64 ]]; then
    printf 'Tool installation currently supports Ubuntu x86_64.\n' >&2
    exit 1
  fi
  local -a root=()
  if (( EUID != 0 )); then
    command -v sudo >/dev/null || { printf 'Run install-tools as root or install sudo.\n' >&2; exit 1; }
    root=(sudo)
  fi
  "${root[@]}" apt-get update -qq
  "${root[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    git curl ca-certificates python3 python3-yaml build-essential unzip xz-utils ripgrep fd-find jq bash-completion eza bubblewrap apparmor \
    fzf bat zoxide btop rsync pkgconf sudo openssh-server
  "${root[@]}" install -m 644 "$repo_dir/config/apparmor/dotfiles-bwrap" /etc/apparmor.d/dotfiles-bwrap
  "${root[@]}" /sbin/apparmor_parser -r /etc/apparmor.d/dotfiles-bwrap
  "${root[@]}" install -d /opt /usr/local/bin
  if ! command -v fd >/dev/null; then
    "${root[@]}" ln -s /usr/bin/fdfind /usr/local/bin/fd
  fi
  if ! command -v bat >/dev/null; then
    "${root[@]}" ln -s /usr/bin/batcat /usr/local/bin/bat
  fi

  download_dir=$(mktemp -d)
  trap 'rm -r -- "$download_dir"' EXIT
  fetch() {
    local name=$1 url=$2 checksum=$3
    curl --fail --silent --show-error --location --retry 3 "$url" -o "$download_dir/$name"
    printf '%s  %s\n' "$checksum" "$download_dir/$name" | sha256sum --check --status
  }

  if [[ $(dua --version 2>/dev/null || true) != 'dua 3.0.3' ]]; then
    fetch dua.tar.gz \
      https://github.com/Byron/dua-cli/releases/download/v3.0.3/dua-v3.0.3-x86_64-unknown-linux-musl.tar.gz \
      68c3142969cf19b29353dbab3c456a483753d49116dbf19ae44ddd545a0abad8
    mkdir "$download_dir/dua"
    tar -xzf "$download_dir/dua.tar.gz" -C "$download_dir/dua"
    local dua_binary
    dua_binary=$(find "$download_dir/dua" -type f -name dua -print -quit)
    "${root[@]}" install -m 755 "$dua_binary" /usr/local/bin/dua
  fi

  if [[ $(nvim --version 2>/dev/null | sed -n '1p' || true) != 'NVIM v0.12.6' ]]; then
    fetch nvim.tar.gz \
      https://github.com/neovim/neovim/releases/download/v0.12.6/nvim-linux-x86_64.tar.gz \
      474430d53e6264f6d6dd18db42d6dc9df3a1b56ca9e88a325bbf860e1a811d87
    "${root[@]}" tar -xzf "$download_dir/nvim.tar.gz" -C /opt
    "${root[@]}" ln -sfn /opt/nvim-linux-x86_64/bin/nvim /usr/local/bin/nvim
  fi
  if [[ $(tree-sitter --version 2>/dev/null || true) != 'tree-sitter 0.27.2'* ]]; then
    fetch tree-sitter.gz \
      https://github.com/tree-sitter/tree-sitter/releases/download/v0.27.2/tree-sitter-linux-x64.gz \
      7ed56d152c52437397b9fcaa43cf341f49933cecc1ca291843f0d347c6e2cb3a
    gzip -dc "$download_dir/tree-sitter.gz" > "$download_dir/tree-sitter"
    "${root[@]}" install -m 755 "$download_dir/tree-sitter" /usr/local/bin/tree-sitter
  fi
  if [[ $(lazygit --version 2>/dev/null || true) != *'version=0.66.3,'* ]]; then
    fetch lazygit.tar.gz \
      https://github.com/jesseduffield/lazygit/releases/download/v0.66.3/lazygit_0.66.3_linux_x86_64.tar.gz \
      0a23f429a95f0d09db298b3c291536d818de066aa5a85c255806f0490ff6656b
    tar -xzf "$download_dir/lazygit.tar.gz" -C "$download_dir" lazygit
    "${root[@]}" install -m 755 "$download_dir/lazygit" /usr/local/bin/lazygit
  fi
  if [[ $(starship --version 2>/dev/null | sed -n '1p' || true) != 'starship 1.27.0' ]]; then
    fetch starship.tar.gz \
      https://github.com/starship/starship/releases/download/v1.27.0/starship-x86_64-unknown-linux-musl.tar.gz \
      10c8eb4cb3b761d9bf59ea828444c2dab36c900b7d69a69e08814b286969df89
    tar -xzf "$download_dir/starship.tar.gz" -C "$download_dir" starship
    "${root[@]}" install -m 755 "$download_dir/starship" /usr/local/bin/starship
  fi
  if [[ $(gh --version 2>/dev/null | sed -n '1p' || true) != 'gh version 2.104.0 '* ]]; then
    fetch gh.tar.gz \
      https://github.com/cli/cli/releases/download/v2.104.0/gh_2.104.0_linux_amd64.tar.gz \
      98cb101ad87dbbd3f6b2f2bfcbd43197ccd07643140121d8a9cfaa91eadbc24e
    tar -xzf "$download_dir/gh.tar.gz" -C "$download_dir" gh_2.104.0_linux_amd64/bin/gh
    "${root[@]}" install -m 755 "$download_dir/gh_2.104.0_linux_amd64/bin/gh" /usr/local/bin/gh
  fi
  printf 'Installed development tools. Continue with the user setup steps in README.md.\n'
}

install_runtimes() {
  if (( EUID == 0 )); then
    printf 'Run install-runtimes as the environment user, not root.\n' >&2
    exit 1
  fi
  curl -fsSL https://mise.run | sh
  curl -LsSf https://astral.sh/uv/install.sh | UV_NO_MODIFY_PATH=1 sh
  export PATH="$HOME/.local/bin:${XDG_DATA_HOME:-$HOME/.local/share}/mise/shims:$PATH"
  mise use --global node@lts
}

grant_sudo() {
  if (( EUID != 0 )) || [[ ! -d /dev/incus ]]; then
    printf 'Run grant-sudo as root inside an Incus environment.\n' >&2
    exit 1
  fi
  id dev >/dev/null
  local policy
  policy=$(mktemp)
  printf 'dev ALL=(ALL:ALL) NOPASSWD: ALL\n' > "$policy"
  visudo -cf "$policy"
  install -m 440 "$policy" /etc/sudoers.d/90-agent-dev
  rm -- "$policy"
}

install_codex() {
  if (( EUID == 0 )); then
    printf 'Run install-codex as the user who will use Codex, not root.\n' >&2
    exit 1
  fi
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
}

install_pi() {
  if (( EUID == 0 )); then
    printf 'Run install-pi as the user who will use Pi, not root.\n' >&2
    exit 1
  fi
  curl -fsSL https://pi.dev/install.sh | sh
}

install_herdr() {
  if (( EUID == 0 )); then
    printf 'Run install-herdr as the user who will use Herdr, not root.\n' >&2
    exit 1
  fi
  curl -fsSL https://herdr.dev/install.sh | sh
  "$HOME/.local/bin/herdr" integration install codex
}

apply_dotfiles() {
  if (( EUID == 0 )); then
    printf 'Run apply-dotfiles as the environment user, not root.\n' >&2
    exit 1
  fi
  local dotfiles_dir
  dotfiles_dir=$(cd -- "${1:?Pass a dotfiles checkout directory}" && pwd -P)
  if [[ -f "$dotfiles_dir/apply.sh" ]]; then
    bash "$dotfiles_dir/apply.sh" apply
    bash "$dotfiles_dir/apply.sh" plugins
  elif [[ -f "$dotfiles_dir/setup-agent.sh" ]]; then
    # Keep pinned dotfiles revisions from before the repository split usable.
    bash "$dotfiles_dir/setup-agent.sh" apply
    bash "$dotfiles_dir/setup-agent.sh" plugins
  else
    printf 'No apply.sh found in %s\n' "$dotfiles_dir" >&2
    exit 1
  fi
}

case "${1:-help}" in
  apply-dotfiles) apply_dotfiles "${2:?Pass a dotfiles checkout directory}" ;;
  install-client)
    if (( EUID == 0 )); then
      printf 'Run install-client as your regular client user.\n' >&2
      exit 1
    fi
    mkdir -p "$HOME/.local/bin"
    client_source="$repo_dir/scripts/agent-env.py"
    replace_client=false
    for option in "${@:2}"; do
      case "$option" in
        --local) client_source="$repo_dir/scripts/agent-env-local.sh" ;;
        --replace) replace_client=true ;;
        *) printf 'Unknown install-client option: %s\n' "$option" >&2; exit 2 ;;
      esac
    done
    client="$HOME/.local/bin/agent-env"
    if [[ -e "$client" || -L "$client" ]]; then
      if [[ -L "$client" && $(readlink "$client") == "$client_source" ]]; then
        :
      elif [[ -L "$client" && "$replace_client" == true ]]; then
        backup_dir="${XDG_STATE_HOME:-$HOME/.local/state}/factory/backups/client-$(date +%Y%m%d-%H%M%S)-$$"
        mkdir -p "$backup_dir"
        mv "$client" "$backup_dir/agent-env"
        printf 'Previous command symlink saved in %s\n' "$backup_dir"
      else
        printf 'Existing command at %s; use --replace for a symlink.\n' "$client" >&2
        exit 1
      fi
    fi
    if [[ ! -e "$client" && ! -L "$client" ]]; then
      ln -s "$client_source" "$client"
    fi
    completion_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
    completion="$completion_dir/agent-env"
    if [[ -e "$completion" || -L "$completion" ]]; then
      if [[ ! -L "$completion" || $(readlink "$completion") != "$repo_dir/completions/agent-env.bash" ]]; then
        printf 'Existing Bash completion at %s; move it aside before installing.\n' "$completion" >&2
        exit 1
      fi
    else
      mkdir -p "$completion_dir"
      ln -s "$repo_dir/completions/agent-env.bash" "$completion"
    fi
    ;;
  install-tools) install_tools ;;
  install-runtimes) install_runtimes ;;
  grant-sudo) grant_sudo ;;
  install-codex) install_codex ;;
  install-pi) install_pi ;;
  configure-codex)
    if (( EUID == 0 )); then
      printf 'Run configure-codex as the user who will use Codex, not root.\n' >&2
      exit 1
    fi
    python3 "$repo_dir/scripts/configure-codex.py"
    ;;
  install-herdr) install_herdr ;;
  install-previews)
    if (( EUID == 0 )); then printf 'Run install-previews as the environment or client user.\n' >&2; exit 1; fi
    python3 "$repo_dir/scripts/install-previews.py"
    ;;
  install-skills) shift; exec python3 "$repo_dir/scripts/install-skills.py" "$@" ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
