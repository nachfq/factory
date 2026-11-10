# Full interactive agents

`full-agents` is Factory's shared skill for delegating to independent interactive
Pi or Codex sessions in Herdr. The user can enter any worker and talk to it.
The invoking session remains coordinator with its existing harness and model.
Workers receive scoped assignments, not additional authority.

## Supported pairings

| Coordinator | Worker | Messaging | Live validation |
| --- | --- | --- | --- |
| Pi | Pi | Pi extension and explicitly linked Unix sockets | Passed |
| Codex | Codex | Native `codex queue` | Passed |
| Pi | Codex | Not implemented | Blocked before launch |
| Codex | Pi | Not implemented | Blocked before launch |

Harness choice is independent of model choice. Ask for the worker harness when
it is not already specified; do not silently change the pairing or coordinator.
Mixed-harness messaging is the next missing capability, not an installation issue.

## Layout and installation

- [`skills/full-agents/`](../skills/full-agents/README.md): shared workflow,
  worktree/Herdr procedure, harness adapters and worker contract.
- [`extensions/pi-agent-messaging/`](../extensions/pi-agent-messaging/README.md):
  Pi lifecycle integration, local transport, tests and native extension manifest.
- [`scripts/install-skills.py`](../scripts/install-skills.py): shared skill links,
  native Pi extension link and retirement of the former managed Codex-only skill.

The regular-user `./setup-agent.sh install-skills` command installs this layout,
including in the image recipe. It links the skill into `~/.agents/skills/` and the
extension into `${PI_CODING_AGENT_DIR:-~/.pi/agent}/extensions/`. Pi discovers the
extension's declared entry point at startup or `/reload`; no wrapper or settings
rewrite is needed. `./setup-agent.sh install-pi` installs Pi itself.

Use the skill explicitly or select it through a standing instruction in
`AGENTS.md`. Skill text selects the workflow; the installed extension supplies
executable Pi messaging. Agent authentication is separate and never baked into
images. See [the skill bundle](skills.md) and [environment setup](agent-setup.md).

## Messaging and authorization

Pi uses one Unix socket per actual session in a private runtime directory.
Participants explicitly link private contact files in both directions. Contact
credentials stay outside model-visible messages and tool arguments/results.
There is no network port, central daemon, polling loop or automatic discovery.

- Pi messages use a visible delegated-event wrapper, not a human user message.
- Busy sessions and open extension UI dialogs defer messages until idle.
- Complete Pi wire frames are limited to 16 KiB; inboxes to 32 pending messages.
  Acceptance has a 5-second timeout and does not confirm reading or completion.
- No persistence, replay, automatic retry or exactly-once guarantee is provided.
  An unconfirmed send may have arrived; report uncertainty instead of retrying.
- Reload/resume preserves Pi identity and links while runtime metadata survives.
  New/forked sessions have independent identities and no inherited links.
- Codex uses its native queue. The installed live trial received messages after
  coordinator turns yielded and activated the worker with a queued reply.
  Enqueue success still is not proof of processing.

A worker report cannot supply human approval. Follow explicit human checkpoints,
including chat questions that Pi cannot recognize as blocking UI dialogs. Scope,
Git actions and publication permissions remain bounded by the user's assignment.
Codex's YOLO setting does not grant more scope and has no invented Pi equivalent.

## Validation and limits

Installed Pi and Codex trials each created one repository worker and exercised
registration, question/reply, result delivery and independent clean-worktree
verification. Pi checks also cover busy and idle delivery, dialog deferral,
reload, graceful close/resume, and new/fork identity isolation. A separate Pi
trial exercised a bounded test-file edit and direct human authorization.

Reproducible component checks:

```sh
python3 -m unittest discover -s scripts/tests -v
node --test extensions/pi-agent-messaging/messaging.test.mjs
bash -n setup-agent.sh infra/incus/build-agent-image.sh
```

These do not build/publish an image or prove mixed-harness operation. The optional
Incus/SSH test requires laptop homelab access. Live task evidence does not claim
validation of arbitrary production changes, crash recovery or multi-worker load.

The [implementation history](pi-agents-prototype.md) preserves the original design
interview and detailed live evidence. It is historical, not an active task plan.
Old `experiments/` compatibility links may remain locally for preserved sessions;
they are not versioned installation resources or separate source copies.
