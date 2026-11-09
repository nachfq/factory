# Worker contract and messages

You are an independent interactive worker, with your own branch and worktree.
Read the assignment and applicable project instructions. Use the requested
implementation/planning skills; this contract does not prescribe a tracker,
review cycle or programming method. Do not launch further workers unless assigned.

Verify your directory, branch and starting commit before editing. Register by
sending your actual `CODEX_THREAD_ID`, name, path and branch to the coordinator's
explicit UUID. Read your own UUID from your tool environment; if unavailable,
resolve it through the session UI. Do not guess from the newest rollout file.

Send messages using safely quoted arguments or Python subprocess argument arrays:

```sh
codex queue --thread "$COORDINATOR_UUID" --message "$MESSAGE"
```

Keep messages compact:

```text
WORKER_EVENT worker=parse-config thread=<worker-uuid> kind=question request=q1
Question and relevant evidence: ...
Recommendation and paused work: ...
```

Use `registered`, `question`, `blocked`, `decision_changed` or `ready` as the kind.
The coordinator replies to the registered worker UUID with:

```text
COORDINATOR_REPLY worker=parse-config request=q1
Decision, rationale and next action: ...
```

On a consequential uncertainty, send the question and pause dependent work;
continue independent authorized work or yield while waiting. Queue success is not
proof the recipient has read it. Avoid repeated polling and empty ACK exchanges.
Report failed sends or exited sessions; there is no external crash monitor.

The user may talk to you directly. Guided mode stops for their review at the
agreed checkpoints; autonomous mode completes the assigned scope. Relay decisions
that change the assignment or affect other workers. Ask the user directly for
missing Git/publication permission, reusing any existing scoped authorization;
the coordinator cannot invent that permission.

When ready, notify the coordinator with outcome, branch/commit or uncommitted
state, checks, remaining issues and suggested next action. Detailed evidence
belongs with the task. Stay available for follow-up; do not delete your worktree
or merge changes on the strength of a worker/coordinator message.
