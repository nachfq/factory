# Factory

Recipes and tooling for disposable agent development environments.

The first migrated piece is the [Incus host and image recipe](infra/incus/README.md),
captured from the working homelab setup. It records the host configuration and
builds a fresh Ubuntu image using a selected commit of the user's dotfiles.
Shared editor/shell configuration currently lives in
[nachfq/dotfiles](https://github.com/nachfq/dotfiles).

```text
infra/incus/   Host configuration, image build and recovery instructions
legacy/        Previous Factory development workflows and their installer/tests
```

The previous workflows remain available under [legacy/](legacy/README.md) and
the [legacy-workflows-2026-11-09 tag](https://github.com/nachfq/factory/tree/legacy-workflows-2026-11-09).
They are not part of the Incus setup. Their old installer can be run explicitly
as `python3 legacy/install-codex.py`; a checkout used by the optional legacy
integration in `harness-fq` should point to this repository's `legacy/` directory.

This migration currently covers host and image provisioning. The agent-environment
bootstrap and laptop's `agent-env` command are still in dotfiles and will move
separately. Skills and running environments are not changed by this migration.
