# Full agents skill

Factory's shared workflow for full interactive Pi and Codex agents. It provides
assignment/review and worktree/Herdr procedures with harness-specific adapters.
It replaces `codex-full-agents`; there is no wrapper command or coordination daemon.

## Supported pairings

- **Pi ↔ Pi:** supported; live messaging, lifecycle and repository-worker trials
  include read-only work and a test-file edit with human authorization and review.
- **Codex ↔ Codex:** validated live through the installed skill and native queue,
  including registration, question/reply, result delivery and independent review.
- **Mixed Pi/Codex or other harnesses:** not implemented; blocked before creating
  tabs/worktrees. Installation alone does not provide cross-harness messaging.

The coordinator asks for Pi or Codex when the choice is not already explicit.
Harness and model are independent choices; the coordinator keeps its current
harness/model. Unsupported pairings are explained, never silently changed.

## Install

As the regular user, from the Factory checkout:

```sh
./setup-agent.sh install-skills --dry-run
./setup-agent.sh install-skills
```

The same command runs in the image recipe. It links:

- `skills/full-agents/` into `~/.agents/skills/full-agents`.
- `extensions/pi-agent-messaging/` into
  `${PI_CODING_AGENT_DIR:-~/.pi/agent}/extensions/pi-agent-messaging`.

Pi's native discovery reads the extension's `package.json` entry point. There is
no wrapper and no settings-file rewrite. Other skills/extensions and existing
Pi settings are preserved; conflicting real files/directories are refused.
`--replace` backs up conflicting symlinks. A previous managed `codex-full-agents`
link is retired; unrelated links are preserved.

The default bundle requires Codex for its pinned third-party plugin. Install Pi
with `./setup-agent.sh install-pi`; the image recipe includes it. Installation
starts no sessions and configures no credentials. See [the bundle guide](../../docs/skills.md).

## Use

Start ordinary `pi` from your project; the extension is discovered automatically.
In an existing Pi session use `/reload` to rediscover installed resources, keeping
the same conversation. Do not restart or replace the coordinator silently.
Invoke `/skill:full-agents`, or request the skill in Codex, then agree on a scoped
task before creating workers.

To make workflow selection persistent, add an instruction to the relevant
`AGENTS.md`, for example:

```text
For delegated work, follow the full-agents skill at ~/.agents/skills/full-agents/SKILL.md.
```

That instruction selects the workflow, not additional task, Git or publication
permission. The installer supplies the executable Pi extension; skill text and
`AGENTS.md` alone do not load code.

Without installation, Pi can load both resources explicitly with its native
`--skill /absolute/path/to/factory/skills/full-agents` and
`-e /absolute/path/to/factory/extensions/pi-agent-messaging/extension.mjs` options.
Before resuming a session, first stop any process writing its exact session file.

## Source layout

Canonical sources live in `skills/full-agents/` and
`extensions/pi-agent-messaging/`. Old `experiments/` compatibility symlinks may
remain locally for preserved sessions; they are ignored, not versioned or used
for installation. Resolve the installed skill symlink before deriving the
extension path.

See [the current guide](../../docs/full-agents.md) for architecture, validation
and limitations, including a link to the archived implementation history.
