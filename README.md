# Factory

Recipes and tooling for disposable agent development environments.

Factory installs the environment's tools and agent defaults, manages its Incus
image recipe, and provides the laptop's `agent-env` command. The user's dotfiles
remain a separate checkout: Factory applies them without owning their contents.

```text
infra/incus/   Host configuration, image build and recovery instructions
infra/netdata/ Optional host monitoring dashboard, separate from agent images
setup-agent.sh Ubuntu tool installation and explicit user setup commands
scripts/       agent-env, Codex defaults and their tests
skills/        Own skills: codex-full-agents, herdr-nvim and sidequestion
skills.yaml    Pinned third-party skill sources (initially Matt Pocock)
config/        Environment system configuration (AppArmor)
legacy/        Previous Factory development workflows and their installer/tests
```

The previous workflows remain available under [legacy/](legacy/README.md) and
the [legacy-workflows-2026-11-09 tag](https://github.com/nachfq/factory/tree/legacy-workflows-2026-11-09).
They are not part of the Incus setup. Their old installer can be run explicitly
as `python3 legacy/install-codex.py`; a checkout used by the optional legacy
integration in `harness-fq` should point to this repository's `legacy/` directory.

See [agent setup](docs/agent-setup.md) for Ubuntu installation, dotfiles integration
and the laptop command, or [the Incus recipe](infra/incus/README.md) for a clean host
and image build. [The skill bundle](docs/skills.md) is installed with
`./setup-agent.sh install-skills` on both the laptop and agent environments.
