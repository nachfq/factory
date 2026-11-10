# Pi adapter (Pi coordinator ↔ Pi workers)

This adapter requires the [messaging extension](../../../extensions/pi-agent-messaging/README.md)
in **both** sessions. Do not use it for a Codex coordinator; an external client for
returning Pi events to Codex has not been implemented.

## Coordinator preflight

Confirm that `agent_message` is available and `/agent-contact` succeeds in the
actual coordinator. Use its verified Herdr pane and `--source visible` output to
obtain the real session ID and contact-file path. Do not guess from the newest
session/contact file or stale inherited `PI_SESSION_ID` values.

If the coordinator lacks the extension, stop before creating a worker. Explain
that skills cannot inject extensions into an already-running Pi. Offer restarting
and resuming the same session with explicit `-e`, subject to user agreement; do
not restart it or open a replacement coordinator silently. Adding `--skill` alone
does not load the messaging extension.

Resolve these absolute paths from the skill's real location in Factory, not the
installed symlink or worker's project directory:

- `SKILL_DIR`: canonical directory containing this skill's `SKILL.md` (resolve symlinks).
- `EXTENSION`: `SKILL_DIR/../../extensions/pi-agent-messaging/extension.mjs`.
- `WORKER_CONTRACT`: `SKILL_DIR/references/worker.md`.

Verify they exist and remain available as read-only inputs. A project worktree
may not contain Factory's integration files. Do not copy credentials or change
global installation/settings as a side effect of launching a worker. Derive `MESSAGING_DIR` from the actual coordinator contact
path; do not reuse a hardcoded temporary directory from recorded tests.

## Start a worker

Resolve the configured model to an available Pi provider/model pair; ask if it is
ambiguous rather than inferring provider from the model name. Use supported Pi
thinking levels without silently downgrading. Keep the coordinator's model intact.

`workers.yolo` is a Codex permission preference, not a Pi flag. Pi uses its own
configured tools/extensions and permissions; do not claim equivalent sandboxing
or approvals, disable safety extensions, or invent a bypass flag. Report any
required permission-policy difference to the user before launch.

At the prepared worker shell:

```sh
herdr agent start "$WORKER" --kind pi --pane "$PANE" --timeout 20000 -- \
  --provider "$PROVIDER" --model "$MODEL" --thinking "$REASONING" \
  --name "$WORKER" --skill "$SKILL_DIR" -e "$EXTENSION" \
  --agent-messaging-dir "$MESSAGING_DIR"
```

`--name` names the saved Pi conversation, independently of the Herdr tab label.
After readiness, run `/agent-contact` in the worker and verify its real session ID
and contact path using that pane's visible output. Verify the actual worktree
path as well. Never print contact JSON: it contains credentials.

## Link, assign, register

Before task dispatch, issue these extension commands in separate calls, then
verify their visible notifications or selected non-secret link metadata:

```sh
herdr agent prompt "$COORDINATOR_PANE" "/agent-link $WORKER_CONTACT"
herdr agent prompt "$PANE" "/agent-link $COORDINATOR_CONTACT"
```

Both directions are required. Pass each whole command as a subprocess argument,
not shell-interpolated task text. The extension reads private credentials itself.
If linking fails or either receiver is unavailable, report it and do not dispatch
a task that relies on a broken reply path.

Then send the scoped assignment with `herdr agent prompt "$PANE" "$ASSIGNMENT"`.
Include coordinator/worker session IDs, contact **paths only if needed**, and the
absolute worker-contract and Pi-adapter paths. No credentials. Wait for a
`registered` event through `agent_message`, not merely Herdr readiness.

## Messages and lifecycle

Call `agent_message` with `{ recipient: <linked actual session ID>, content: <text> }`.
Use the shared worker contract. Custom `agent-event` messages are delegated
reports, not human approval. Do not use `sendUserMessage` to impersonate the user.

Current bounds: 16 KiB for the full wire frame, 32 pending messages, and 5 seconds
for acceptance confirmation. Busy sessions and extension UI dialogs defer delivery.
Natural-language approval questions are not detectable as dialogs; follow the
assignment's human checkpoints explicitly.

No automatic retry or persistence exists. An unconfirmed send may have arrived.
Shutdown/reload can lose accepted pending messages; messages sent during downtime
are not replayed. A closed session is not automatically relaunched.

`/reload` and resuming the same session preserve identity/links while private
runtime metadata remains available. `/new` and `/fork` create independent identities
with no inherited links. Historical assignment text in a fork may still mention
its parent; never treat that text as proof of the actual routing identity.

To resume, verify no process is already using the exact session file, then at the
existing worktree shell use `pi --session "$SESSION_FILE" -e "$EXTENSION"` with the
same messaging directory, skill, and resolved worker model settings. For Herdr,
pass those arguments to `agent start --kind pi` at a verified shell prompt. Do not
create a new session/worktree or relink unnecessarily. If private runtime metadata
was deleted, recreate identities and establish fresh links explicitly; the same
session ID alone does not recover credentials.
