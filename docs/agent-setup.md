# Agent environment setup

Factory owns tool installation and agent defaults. A separate dotfiles checkout
owns its editor, shell and Herdr configuration. The default dotfiles source is
[nachfq/dotfiles](https://github.com/nachfq/dotfiles).

## Existing Ubuntu environment

The supported tool-install target is Ubuntu 24.04 x86_64. Run the root steps
inside the Incus environment. For a checkout at `/home/dev/factory`:

```bash
incus exec ENVIRONMENT -- bash /home/dev/factory/setup-agent.sh install-tools
incus exec ENVIRONMENT -- bash /home/dev/factory/setup-agent.sh grant-sudo
```

`grant-sudo` requires Incus and grants `dev` passwordless sudo inside that
environment. It does not alter host sudo permissions. The standard image recipe
creates this user and runs these steps automatically.

As the environment's regular user, after cloning Factory and your dotfiles:

```bash
cd ~/factory
./setup-agent.sh install-runtimes
./setup-agent.sh install-codex
./setup-agent.sh configure-codex
./setup-agent.sh install-herdr
./setup-agent.sh apply-dotfiles ~/dotfiles
```

The last command calls the dotfiles checkout's `apply.sh apply` and
`apply.sh plugins`. It does not contain a second copy of those configs. Older
pinned dotfiles revisions with `setup-agent.sh apply/plugins` remain supported.
Applying configs is explicit: the other commands leave editor/shell config alone.

The tooling remains the same as before the repository split:

- CLI tools, compiler/build basics, Python, Neovim, Tree-sitter CLI, GitHub CLI,
  LazyGit, Starship and the terminal utilities used by the existing setup.
- Mise, Node LTS/npm, and uv through their official installers.
- Codex using `curl -fsSL https://chatgpt.com/codex/install.sh | sh`, with no
  Codex version pin. Re-run `install-codex` to update.
- Codex defaults: `gpt-6.1-sol`, reasoning `high`, full access and no approval
  prompts. `configure-codex` preserves other settings and hook trust, backs up
  changes under `~/.local/state/factory/backups`, and leaves auth files alone.
- Herdr through its official installer, with its Codex integration.

The environment's AppArmor policy remains named `dotfiles-bwrap` for compatibility
with previous images; its source is now `config/apparmor/dotfiles-bwrap` in Factory.
It allows Bubblewrap user namespaces. Using Codex's optional internal sandbox
also requires enabling nesting on that particular Incus instance. The usual
full-access agent workflow uses the container as its isolation boundary.

Rust, browsers, Docker daemons and project services remain project additions.
GitHub/Codex logins belong to each environment and are configured separately.
New Codex sessions use changed defaults; use `/model` in an already-open session
to change that session's model/reasoning choice.

## Laptop command

From the Factory checkout on the laptop:

```bash
./setup-agent.sh install-client
```

This installs only `~/.local/bin/agent-env`. It does not install Ubuntu tools or
apply dotfiles to the laptop. To migrate the old dotfiles-owned command symlink,
use `install-client --replace`; it backs up that symlink first. Real files are
never replaced by this command.

Run the following inside a **local laptop Herdr pane**:

```bash
agent-env new demo
agent-env new project https://github.com/OWNER/REPOSITORY.git
agent-env list
agent-env open demo
agent-env remove demo
```

The defaults remain host `nacho@homelab` and image `agent-base`. Set
`AGENT_ENV_HOST` / `AGENT_ENV_IMAGE` to target a different host or image. See
[Incus setup](../infra/incus/README.md) for the required profile/network/pool.

`new` provisions the laptop's SSH public key, pins guest SSH host keys obtained
through Incus, copies Git name/email, and creates `~/NAME` in instance `dev-NAME`.
It applies the laptop's version of the Codex defaults even when the cached image
is older. Private clones that need login leave the environment ready for manual
authentication and cloning. New SSH provisioning handles the image's first-boot
service restart limit before connecting.

Herdr gets a project workspace with an editor on the right and a shell or
authenticated Codex on the left. `open` starts a stopped environment and reconnects
without duplicating the profile/workspace. Existing running panes stay intact.
After a server restart it can restore the editor/agent in its managed shell panes.
`remove` permanently deletes the managed container and local connection entries;
it does not check for unpushed work or ask for confirmation.

Local runtime connection state remains under `~/.local/state/agent-env/`, with SSH
configuration in `~/.ssh/agent-env.conf` and pinned host keys in
`~/.ssh/agent-env_known_hosts`. The user SSH private key is not copied to guests.

## Checks

```bash
python3 -m unittest discover -s scripts/tests -v
```

For the opt-in check against the real homelab image, which creates and deletes
only its own uniquely named test container and adds no Herdr connection:

```bash
AGENT_ENV_INTEGRATION=1 python3 -m unittest discover -s scripts/tests -v
```
