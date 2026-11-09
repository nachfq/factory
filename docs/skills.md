# Shared skill bundle

Factory owns both our skills and the list of external skills to install:

```text
skills/
  codex-full-agents/   Independent Codex sessions, branches and Herdr tabs
  herdr-nvim/          Selection reading, file display and temporary highlights
skills.yaml           External repositories, exact revisions and skill paths
```

Our two skills moved from `harness-fq` and the local `herdr-codex.nvim` checkout.
The editor plugin remains a separate project. Personal desktop notes and
`sidequestion` remain in `harness-fq` and are not part of the common image.

## Install

As the regular user on the laptop or inside a prepared agent environment:

```bash
cd /path/to/factory
./setup-agent.sh install-skills --dry-run
./setup-agent.sh install-skills
```

Requires Git, Python 3.10+ and PyYAML (`python3-yaml` on Ubuntu; `python-yaml`
on Arch). The Ubuntu tool installation includes that package. The image recipe
runs this command after installing tools and applying dotfiles.

Own skills link directly from this checkout into `~/.agents/skills/`. External
repositories are fetched at the exact commit in `skills.yaml`, under
`${XDG_DATA_HOME:-~/.local/share}/factory/skill-sources/NAME/REVISION/`.
The configured `path` links into the same skills directory. A path may identify
one skill or a directory containing a collection. Upstream licenses, plugin
metadata and skill invocation policies remain in their original checkout.
This currently preserves the `mattpocock-skills:` namespace and all 38 skills
from the existing local installation, pinned to
`59db609eb1e18aaf59b63284d0e52255aff0c63c`.

Third-party source is not copied into Factory's Git history. Sources live in
the data directory rather than a cache, so cleaning the image's cache preserves
installed skill targets. GitHub/Codex logins are not needed for public sources
and are never included in the bundle.

For the initial migration of the old editor/Matt symlinks, or when updating an
external revision:

```bash
./setup-agent.sh install-skills --replace
```

`--replace` preserves conflicting symlinks under
`~/.local/state/factory/backups/`; it refuses real files/directories. All target
conflicts are checked before changing links. Existing unrelated skills are
preserved. Re-running the command reuses a verified clean pinned checkout and
keeps matching links. Local edits to third-party checkouts cause an error so
they can be preserved before updating. Skills are available on the next Codex
turn; an existing image or environment is not automatically updated by a push.

## Add, remove or update

Add an own skill under `skills/NAME/SKILL.md` and rerun the installer. Keep its
helpers and references beside it. Edit these own files through their active
symlinks or the checkout; review and commit the resulting Factory diff.

For an external skill or collection, add an entry to `skills.yaml` with:

```yaml
- name: another-skill
  repository: https://github.com/OWNER/REPOSITORY.git
  revision: FULL_40_CHARACTER_COMMIT
  path: path/to/skill
```

Pin updates by changing `revision`, running `install-skills --replace`, and
testing the intended behavior before committing. A rollback uses the previous
manifest revision and the same command. Retired revisions remain on disk until
explicit cleanup; running sessions can still refer to them.

Remove an entry or own skill and rerun the installer. It removes only retired
links recorded by its previous install that still point at the managed source;
it preserves replacements and unrelated skills. Its local record is
`~/.local/state/factory/skills.json`.

## Full agents and editor integration

Full-agent worker preferences live in `~/.config/factory/config.json`. On the
laptop, the first install copies only `workers` from the former
`~/.config/harness-fq/config.json`; personal profiles/context are left there.
Existing Factory preferences are preserved. Fresh environments get a worktree
directory, GPT-6.1 Sol/high implementers, xhigh reviewers, full access (YOLO)
and the agent/Neovim/LazyGit layout. The skill also supports the former config
as a fallback when used independently. Worker creation still requires an
explicit user assignment and a local Herdr session.

`herdr-nvim` supplies instructions and a native Neovim display helper. The
optional `nvim-selection` MCP and selection/request-card plugin integration
must be installed separately; installing the skill alone does not configure
MCP or copy laptop sockets into an environment. Native file display uses a
verified editor socket in the same environment.

## Checks

```bash
python3 -m unittest discover -s scripts/tests -v
```

Installer tests use temporary homes and a real local Git repository, with no
public network or live credentials. They exercise pinned fetches, revisions,
backups, conflicts, retirement, modified sources and preference migration.
