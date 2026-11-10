# Codex adapter (Codex coordinator ↔ Codex workers)

Use Codex's native queue for communication between full interactive Codex
sessions. This is the Codex adapter of the shared `full-agents` skill. Do not use
it with a Pi coordinator: `codex queue` cannot address a Pi session, and a return
bridge has not been implemented.

## Start and name

Use the shared Herdr/worktree instructions. Validate `workers.yolo` as a boolean.
When false, `PERMISSION_ARGS` is an empty Bash array; when true, it contains only
`--dangerously-bypass-approvals-and-sandbox`. This affects execution permissions,
not scope, human checkpoints, Git authorization, or global settings. Let the user
handle permission prompts.

Build `REASONING_OVERRIDE` as TOML, such as `model_reasoning_effort="high"`:

```sh
herdr agent start "$WORKER" --kind codex --pane "$PANE" --timeout 20000 -- \
  --model "$MODEL" -c "$REASONING_OVERRIDE" "${PERMISSION_ARGS[@]}"
```

Name the saved conversation in a separate idle-composer operation:

```sh
herdr agent prompt "$PANE" "/rename $WORKER"
```

Inspect the pane and confirm naming completed before assignment dispatch. Startup
readiness and a tab label do not establish the worker's actual Codex thread ID.

## Assign and message

The coordinator must have its actual Codex thread UUID. Send the scoped assignment
through Herdr with coordinator identity and the absolute worker-contract path.
The worker registers its actual `CODEX_THREAD_ID`, obtained from its own tool
environment or verified session UI, not the newest rollout file.

Use safely quoted arguments or Python subprocess arrays for messages:

```sh
codex queue --thread "$RECIPIENT_THREAD_ID" --message "$MESSAGE"
```

A successful queue command means enqueued, not processed. The installed live
trial delivered registration/question/ready after coordinator turns yielded;
the queued reply activated the worker without a manual wake-up. Still verify the
recipient's actual response rather than treating enqueue success as processing.
Keep the common event conventions and review boundaries. Never pass a Pi ID to `codex queue`, even if it
looks like a valid UUID. Report failed sends or exited sessions; no external crash
monitor or automatic restart is provided.

## Resume

Reuse the exact registered thread and existing worktree/branch:

```sh
codex -C "$WORKTREE" "${PERMISSION_ARGS[@]}" resume "$WORKER_THREAD_ID"
```

With Herdr, start at a verified worktree shell and pass `resume UUID` to
`agent start --kind codex`, retaining the resolved model/reasoning/permission
arguments as applicable. Do not use `codex --worktree`, create another thread, or
resend the initial assignment blindly. Use `codex resume --all` only if the exact
UUID or unambiguous saved name is lost. A new coordinator thread must explicitly
supply its new reply UUID to existing workers.
