# Shared skill bundle

Factory owns both our skills and the list of external skills to install:

```text
skills/
  full-agents/         Shared Pi/Codex workflow; Pi messaging validated, mixed blocked
  herdr-nvim/          Selection reading, file display and temporary highlights
skills.yaml           External repositories, exact revisions and skill paths
```

Our skills moved from `harness-fq` and the local `herdr-codex.nvim` checkout.
The editor plugin remains a separate project. Personal desktop notes remain in
`harness-fq`; the generic skills belong to the common image. `full-agents`
replaces the former `codex-full-agents` skill with shared harness adapters.

## Install

As the regular user on the laptop or inside a prepared agent environment:

```bash
cd /path/to/factory
./setup-agent.sh install-skills --dry-run
./setup-agent.sh install-skills
```

Requires Git, Python 3.11+, Codex with native plugin commands, and PyYAML
(`python3-yaml` on Ubuntu; `python-yaml` on Arch). The Ubuntu tool installation
includes that package. The image recipe
runs this command after installing tools and applying dotfiles.

Own skills link directly from this checkout into `~/.agents/skills/`.
`full-agents` is an ordinary skill; it adds no wrapper command. The installer also
links `extensions/pi-agent-messaging/` into
`${PI_CODING_AGENT_DIR:-~/.pi/agent}/extensions/pi-agent-messaging` for Pi's native
auto-discovery. Its manifest declares the `.mjs` entry point. This uses the same
conflict checks and managed-link ledger, without rewriting settings or starting
agents. Install Pi separately with `./setup-agent.sh install-pi`; the image recipe
includes that step. The former managed `codex-full-agents` link is retired.

Matt is installed with Codex's native plugin manager, using the upstream
marketplace and plugin manifests. The equivalent commands for the current pin
are:

```bash
codex plugin marketplace add https://github.com/mattpocock/skills.git --ref 59db609eb1e18aaf59b63284d0e52255aff0c63c
codex plugin add mattpocock-skills@mattpocock
```

Codex records the marketplace ref in its normal configuration and owns the
installed plugin/cache. Factory does not vendor or rewrite Matt's skills.
This loads the 27 skills declared by the author's plugin; the former raw
repository link exposed 38, including skills outside that published selection.
The native installation keeps the `mattpocock-skills:` namespace and upstream
invocation policies. The old Factory-managed Matt link is removed only after
the native install succeeds, so it does not create duplicate skill entries.

The Matt entry also sets `pi_skills: true`. For Pi, the installer fetches the same
pinned source and exposes only the 27 directories declared in the upstream
`.claude-plugin/plugin.json`, through a managed collection link under
`${PI_CODING_AGENT_DIR:-~/.pi/agent}/skills/`. The generated link bundle lives in
`${XDG_DATA_HOME:-~/.local/share}/factory/pi-skill-bundles/NAME/REVISION/`;
upstream files and licenses remain unchanged in the source checkout. Pi uses
ordinary skill names rather than Codex's plugin namespace. Keeping this link
outside `~/.agents/skills/` avoids duplicating the native plugin in Codex.

External entries without `kind: codex-plugin` remain ordinary skill sources.
They are fetched at the manifest's exact commit, under
`${XDG_DATA_HOME:-~/.local/share}/factory/skill-sources/NAME/REVISION/`, and the
configured `path` is linked into the skills directory. A path may identify one
skill or a collection. Upstream licenses and metadata remain in that checkout.

Third-party source stays out of Factory's Git history. Both native plugin data
and ordinary sources survive the image recipe's cache cleanup. Public sources
need no GitHub/Codex login; credentials are never included in the bundle.

For the initial migration of old skill/command symlinks, or when updating an
external revision:

```bash
./setup-agent.sh install-skills --replace
```

`--replace` preserves conflicting symlinks under
`~/.local/state/factory/backups/`; it refuses real files/directories. Native
plugin changes also preserve a private copy of the existing Codex configuration.
Changing a native plugin pin reinstalls that plugin through Codex, including
when upstream kept the same plugin version across commits. All target
conflicts are checked before changing links. Existing unrelated skills are
preserved. Re-running keeps matching links and installed native plugins.
Ordinary third-party checkouts are verified clean; local edits cause an error
so they can be preserved before updating. Skills are available on the next Codex
turn. Pi discovers the shared `~/.agents/skills/` directory at startup or with
`/reload`; loading skills alone does not activate extensions. An existing image
or environment is not automatically updated by a push.

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

For a native plugin, also set `kind: codex-plugin`, `marketplace` and `plugin`,
as in the Matt entry. Factory invokes Codex to manage that installation.
Set `pi_skills: true` to also expose its published skill list to Pi; this expects
an explicit `skills` array in `.claude-plugin/plugin.json` beside the configured
skill-source directory.

Pin updates by changing `revision`, running `install-skills --replace`, and
testing the intended behavior before committing. A rollback uses the previous
manifest revision and the same command. Ordinary source revisions remain on
disk until explicit cleanup. Codex manages the lifetime of native plugin caches.

Remove an entry or own skill and rerun the installer. It removes only retired
links that still point at its recorded managed source. Retired native plugins
are removed only when their marketplace source/ref still matches the managed
record. Replacements and unrelated skills are preserved. Local records live in
`~/.local/state/factory/skills.json` and `plugins.json`.

## Full agents and editor integration

Use the installed `full-agents` skill for scoped delegation, explicitly with
`/skill:full-agents` in Pi or through a standing instruction in `AGENTS.md`.
There is no separate launcher command. Agree on an assignment before creating
workers; persistent instructions do not grant additional authorization.

Pi needs `extensions/pi-agent-messaging/extension.mjs` loaded in both coordinator
and workers. After installation, ordinary Pi startup or `/reload` discovers the
installed extension automatically. No wrapper or settings-file edit is needed.
Skills and `AGENTS.md` select instructions; the installed extension supplies
executable messaging. Do not open a second writer on a live session. See [the skill guide](../skills/full-agents/README.md)
for supported pairings and [the extension guide](../extensions/pi-agent-messaging/README.md)
for linking and delivery semantics. Both Pi↔Pi and Codex↔Codex have live evidence
through the installed shared skill, including registration, question/reply and
result delivery. Mixed-harness workers remain blocked.
The shared skill is the only full-agent entry point; Codex sessions still require
their own authentication, which is intentionally absent from images.

Full-agent worker preferences live in `~/.config/factory/config.json`. On the
laptop, the first install copies only `workers` from the former
`~/.config/harness-fq/config.json`; personal profiles/context are left there.
Existing Factory preferences are preserved. Fresh environments get a worktree
directory, GPT-6.1 Sol/high implementers, xhigh reviewers, full access (YOLO)
and the agent/Neovim/LazyGit layout. YOLO is Codex-only; Pi keeps its own tool
and permission policy. The skill also supports the former config
as a fallback when used independently. Worker creation still requires an
explicit user assignment and a local Herdr session.

`herdr-nvim` uses native Neovim socket helpers for both Pi and Codex: identify
an editor with `scripts/read_selection.py --server SOCKET --metadata`, read its
selection without `--metadata`, or navigate with `scripts/show_file.py`. Resolve
these helper paths from the skill directory and verify the editor belongs to
the intended Herdr tab before reading. Selection reads include unsaved text and
consume each capture once. They require the editor's `herdr-codex.context`
module, not an MCP server. For direct sending, the editor's separate `<leader>a`
request card lets the user choose Pi or Codex; `Enter` submits and `Ctrl+s` stages
in the recipient's draft. Installing the skill does not install the editor
module or copy laptop sockets into an environment.

## Checks

```bash
python3 -m unittest discover -s scripts/tests -v
```

Installer tests use temporary homes and a real local Git repository, with no
public network or live credentials. They exercise pinned fetches, revisions,
backups, conflicts, retirement, modified sources and preference migration.
When Codex is installed, native plugin tests use the same local Git fixture to
verify migration, pinned updates and retirement without public network access.
Run the model-free messaging suite separately:

```sh
node --test extensions/pi-agent-messaging/messaging.test.mjs
```
