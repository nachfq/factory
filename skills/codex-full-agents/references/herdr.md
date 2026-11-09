# Worktrees and visible terminals

Read when launching or resuming a worker. Check installed CLI help when an API
differs. Use argument arrays for subprocesses; never interpolate task text into
shell code. Herdr is a terminal adapter; messages use Codex itself.

## Worktree

Inspect `git status --short`, `git worktree list --porcelain`, branches and
remotes. Resolve the intended base to a commit. Uncommitted coordinator changes
are not included in a new worktree: settle any dependency on them before launch.

Use `WORKTREES_ROOT/OWNER/REPO/WORKER`, deriving identity from the intended Git
remote. Validate components and resolved path containment; reject path traversal.
The storage root must exist and be writable, including its symlink destination.
Do not silently fall back to another disk. Reuse a matching existing worktree
when resuming; inspect collisions rather than replacing them.

```sh
git -C "$REPO" worktree add -b "$BRANCH" "$WORKTREE" "$BASE_SHA"
```

Use a short worker name and a related branch such as `work/parse-config`.
Verify branch, HEAD and repository after creation. Do not also use
`codex --worktree`, copy ignored output/secrets, or share mutable build artifacts.

## Herdr

Check `herdr workspace list`, `herdr pane list` and `herdr agent list`. Match the
original repo/coordinator to its workspace using verified paths and pane state;
environment IDs and current focus can be stale. Never launch in the user's
unrelated focused workspace. If Herdr is unavailable, explain that and provide
the direct interactive command; do not silently replace the terminal adapter.

```sh
herdr tab create --workspace "$WORKSPACE" --cwd "$WORKTREE" --label "$WORKER" --no-focus
```

Retain `result.tab.tab_id` and `result.root_pane.pane_id`. The original pane is
the worker's pane, including when an editor split is added.

`workers.yolo` must be a boolean. Set `PERMISSION_ARGS` to an empty Bash array
when false, or `(--dangerously-bypass-approvals-and-sandbox)` when true. This
changes execution permissions, not scope, human checkpoints or Git authorization.
Do not change global Codex permissions. Let the user handle any permission prompt.

```sh
herdr agent start "$WORKER" --kind codex --pane "$PANE" --timeout 20000 -- \
  --model "$MODEL" -c "$REASONING_OVERRIDE" "${PERMISSION_ARGS[@]}"
```

Build `REASONING_OVERRIDE` as TOML, for example `model_reasoning_effort="high"`.
Do not silently replace an unavailable requested model. If startup fails or
times out, inspect `pane process-info` and `pane read` before retrying: a Codex
process may already be running. Never send shell commands into its composer.

Name the saved chat with `/rename WORKER` in the idle Codex composer, separately
from the Herdr label. Check that this completed before submitting the assignment:

```sh
herdr agent prompt "$PANE" "/rename $WORKER"
herdr pane read "$PANE" --source recent-unwrapped --lines 12 --format text
herdr agent prompt "$PANE" "$ASSIGNMENT"
```

Use separate calls for the rename, inspection and dispatch. Do not submit twice
after an ambiguous result. Verify the assignment was received and the worker
registers its UUID. Keep the user's current focus unchanged.

## Editor layout

`workers.herdr.layout` accepts `agent` or `agent-nvim-lazygit`; reject other values.
For the latter, add an editor to the right after creating the tab, before task
dispatch. Check `nvim`, `lazygit` and the user's LazyVim/Snacks setup first.

```sh
herdr pane split --pane "$PANE" --direction right --ratio 0.5 --cwd "$WORKTREE" --no-focus
```

Retain `result.pane.pane_id` as the editor pane. At its fresh shell prompt, launch
Neovim with LazyGit already open, using one safely quoted command:

```python
import shlex
import subprocess

editor_args = ["nvim", "-c", "autocmd User VeryLazy ++once lua vim.schedule(function() "
               "Snacks.lazygit({ cwd = LazyVim.root.git() }) end)"]
subprocess.run(["herdr", "pane", "run", editor_pane, shlex.join(editor_args)], check=True)
```

Verify the editor process and visible output. `q` returns from LazyGit to Neovim.
If the editor cannot start, report the missing component and keep the authorized
worker in its original pane. Do not install dependencies or duplicate an existing
split. Both panes use the same worktree; the editor is for the user.

## Resume

Reuse the existing branch/worktree and registered thread UUID:

```sh
codex -C "$WORKTREE" "${PERMISSION_ARGS[@]}" resume "$WORKER_THREAD_ID"
```

For Herdr, open a tab at that worktree and pass `resume UUID` to `agent start`.
Do not create another worktree/session or resend the original task blindly.
If the coordinator is a new session, send its new UUID to the existing workers.
Use `codex resume --all` only when the exact UUID or unambiguous saved name is lost.
Live sessions and worktrees remain local to this machine.
