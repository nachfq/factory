# Shared worktrees and visible terminals

Read with the selected harness adapter. Use subprocess argument arrays; never
interpolate assignments, paths, or user text into shell code. Check installed CLI
help when APIs differ. Herdr handles terminals, not message delivery.

## Worktree

Inspect `git status --short`, `git worktree list --porcelain`, branches, and remotes.
Resolve the intended base to a commit. Settle dependencies on uncommitted changes
before launch; never copy ignored secrets or mutable build artifacts into workers.

For repository assignments use `WORKTREES_ROOT/OWNER/REPO/WORKER`, deriving identity
from the intended Git remote. If repository identity or base is ambiguous, resolve
it before creation. Validate path components and resolved containment; reject path
traversal. The root must already exist and be writable, including any symlink
backing storage. Do not silently select another disk.

Reuse matching worktrees on resume. Inspect collisions rather than replacing them.
For a new worker, use a short name and a related branch such as `work/parse-config`:

```sh
git -C "$REPO" worktree add -b "$BRANCH" "$WORKTREE" "$BASE_SHA"
```

Verify repository, branch, and HEAD afterward. Do not also use a harness-managed
worktree flag. Non-repository messaging demonstrations require an explicitly
agreed exception; do not treat those as validation of a coding-worker workflow.

## Herdr

Check `herdr workspace list`, `herdr pane list`, and `herdr agent list`. Verify the
coordinator's actual pane/tab and repository paths. Environment IDs and current
focus can be stale. Never launch into an unrelated focused workspace.

If Herdr is unavailable, explain and provide the direct interactive command;
do not silently substitute another terminal adapter.

```sh
herdr tab create --workspace "$WORKSPACE" --cwd "$WORKTREE" --label "$WORKER" --no-focus
```

Retain `result.tab.tab_id` and `result.root_pane.pane_id`. The root pane remains the
worker pane even when an editor split is added. Start the agent using the selected
adapter, at a verified fresh shell prompt. Preserve user focus.

If startup fails or times out, inspect `herdr pane process-info --pane "$PANE"`
and `herdr pane read "$PANE" --source visible --format text` before retrying. A live
agent may already exist. Never send shell commands into an agent composer.

Use separate calls for naming, verification, and assignment dispatch. Do not submit
the same assignment twice after an ambiguous result. Check receipt and registration.
Herdr's status is useful for readiness, but is not authoritative for Pi dialogs;
the live test showed a visible confirmation without `blocked` status.

## Optional editor

`workers.herdr.layout` accepts only `agent` or `agent-nvim-lazygit`. For the latter,
check `nvim`, `lazygit`, and the user's LazyVim/Snacks setup, then add the editor
before assignment dispatch. Do not install missing dependencies or duplicate splits.

```sh
herdr pane split --pane "$PANE" --direction right --ratio 0.5 --cwd "$WORKTREE" --no-focus
```

Retain `result.pane.pane_id` as the editor pane. At its fresh shell prompt:

```python
import shlex
import subprocess

editor_args = ["nvim", "-c", "autocmd User VeryLazy ++once lua vim.schedule(function() "
               "Snacks.lazygit({ cwd = LazyVim.root.git() }) end)"]
subprocess.run(["herdr", "pane", "run", editor_pane, shlex.join(editor_args)], check=True)
```

Verify the editor process/output. `q` returns from LazyGit to Neovim. If the editor
cannot start, report the issue and retain the authorized worker in its original
pane. Both panes use the same worktree; the editor is for the user.

## Resume

Reuse the existing branch/worktree and exact registered session. Check for an
already running participant before starting another writer. Each harness adapter
supplies its resume command. Do not resend the original assignment blindly.

If the coordinator is a new conversation, its old identity is not transferable.
Re-establish the reply route explicitly and send updated coordinator information
before assigning further work. Sessions/worktrees remain local; no automatic
cleanup or publication is implied.
