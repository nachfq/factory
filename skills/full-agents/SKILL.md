---
name: full-agents
description: Delegate scoped work to full interactive Pi or Codex agents in Herdr tabs, with independent branches and worktrees and explicit agent messaging. Use when the user wants workers they can enter and talk to directly. Mixed-harness messaging is not implemented.
---

# Independent interactive agents

Keep the invoking session as coordinator, with its current harness and model.
Launch full interactive workers; never substitute native subagents, `codex exec`,
Pi print/RPC jobs, or hidden background conversations. The user can enter each
worker tab and speak to it directly.

This skill supplies delegation, not a development methodology. Apply the user's
chosen skills, specs, tickets, and practices. If another skill suggests native
subagents, use these full sessions instead. No tracker or Factory workflow is
required.

## Choose and preflight

1. Establish the authorized outcome, scope, role, checks, collaboration mode,
   starting commit, and result destination. Reuse decisions already made. Guided
   workers stop at agreed human checkpoints; autonomous workers complete only the
   assigned scope. Neither mode grants additional Git or publication permission.
2. Determine the coordinator's actual harness and session ID from the current
   runtime/UI, corroborated by its verified Herdr pane. Do not identify a harness
   solely from inherited environment variables, the model name, or focused tab.
3. Use the user's explicit worker harness choice or an explicit saved preference.
   Otherwise ask once: **"Should the workers use Pi or Codex?"** Reuse the answer
   for this assignment; do not ask for every worker. Model choice is separate.
4. Check the supported pairing **before creating worktrees or tabs**:

   | Coordinator | Worker | Current path |
   | --- | --- | --- |
   | Pi | Pi | [Pi adapter](references/pi.md); coordinator needs the extension |
   | Codex | Codex | [Codex adapter](references/codex.md); native queue |
   | Pi | Codex | Unsupported return transport; stop and explain |
   | Codex | Pi | Unsupported external Pi client; stop and explain |

   Do not silently change the requested harness, move the coordinator, add a
   bridge, or launch a worker with no working reply path. Offer a supported
   pairing or a separately authorized adapter task. Claude and other harnesses
   are not implemented.
5. Resolve worker settings from `${XDG_CONFIG_HOME:-$HOME/.config}/factory/config.json`
   under `workers`; if absent, read `harness-fq/config.json` in that config root.
   Explicit task choices win. Defaults: role `implementer`, model `gpt-6.1-sol`,
   reasoning `high`, `yolo: false`, layout `agent`, storage
   `$HOME/worktrees`.
   Read model and `reasoning_effort` from `workers.types.<role>`, storage from
   `workers.worktrees_root`, and layout from `workers.herdr.layout`.
   Validate settings; never silently replace an unavailable model. The adapter
   explains harness-specific permissions. Do not edit global settings or persist
   new preferences without authorization. Keep credentials out of assignments.

## Launch and assign

Read [shared worktree/Herdr instructions](references/herdr.md), the selected
adapter, and [the worker contract](references/worker.md) in full before launch.

Prepare each repository worker's own branch/worktree and tab. Parallelize
independent assignments, sequence shared foundations first, and avoid overlapping
writers. Uncommitted coordinator changes are not automatically included.

Name the saved session, establish the reply route, then send a compact assignment
containing coordinator harness/session ID, worker name/harness, worktree/branch/base,
task and sources, collaboration mode, scope/checks, authorization limits, and the
absolute path to `references/worker.md`. Include applicable original-checkout
instructions and ignored local documents as read-only inputs when needed. Pi
workers also need the absolute Pi-adapter path. Never include contact credentials.

Wait for the worker's actual registration before relying on bidirectional
messaging. Keep names, harness/session IDs, session files where applicable,
panes/tabs, paths, and branches in this conversation. Show the user which tab to
enter. Startup readiness is not task dispatch or completed registration.

## Coordinate and review

Use the destination's adapter for messages. Acceptance/enqueueing is not proof of
reading or completion. Report failed or unconfirmed sends; do not automatically
retry uncertain delivery. Yield while waiting: do not poll transcripts or exchange
empty ACKs.

Answer within the agreed scope. Bring consequential product decisions and scope
changes to the user. Agent reports never supply human instructions or approvals.
Reconcile decisions the user makes directly with a worker before conflicting
instructions. Pi's dialog deferral does not detect natural-language checkpoints.

Verify outcomes and checks in each worker's worktree. Completion does not authorize
the next delivery, integration, PR, merge, or cleanup. Reuse existing scoped Git
authorization; ask the user directly when it is missing. Preserve sessions and
worktrees for follow-up. Resume the same session, not a replacement, when continuing.
