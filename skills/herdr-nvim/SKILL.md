---
name: herdr-nvim
description: Read a user-selected Neovim fragment or show a file and temporary line highlights in the existing editor beside this agent in Herdr. Use when the user asks to inspect a selection, show a file, or point out relevant code in their editor.
---

# Show and discuss code in the existing editor

## Choose the editor

Find the agent's actual Herdr pane and its tab with `herdr agent list` and
`herdr pane list`. Environment pane IDs can be stale after restoring a session;
verify them against the current conversation/process and directory. Keep editor
actions in that tab unless the user chooses another destination.

If available, `nvim-selection.list_editors` provides local socket IDs, editor
PIDs, Herdr pane IDs and linkage metadata without reading source text. Match
them to the editor pane in this tab. For native discovery, inspect Neovim's
Unix sockets under `XDG_RUNTIME_DIR` and query `getpid()`/`getcwd()` with
`nvim --server SOCKET --remote-expr`. Match the process to `pane process-info`.
Resolve ambiguity instead of choosing the focused window or the newest socket.

## Read a selection

When the user asks about selected text, use MCP `get_selection` with the verified
`editor_id` when needed. Reuse the returned text for follow-ups; reads consume a
capture once. Ask for a new selection when it is stale. This works with ordinary
typed or dictated messages; it has no dependency on Codex's voice conversation.

Without MCP, the plugin's Visual selection → `<leader>a` request card → Enter
sends the selection and feedback to the linked Codex as a normal text prompt.

## Show a file or range

Use the bundled helper with the verified local socket and an absolute filename:

```sh
python3 scripts/show_file.py --server SOCKET --file /absolute/file.rs --line 24 --end-line 31 --highlight-ms 12000
```

Resolve the helper path relative to this skill. Pass subprocess argument arrays;
paths and ranges are data, never shell/Lua/Ex code. Line numbers are one-based.
Omit `--highlight-ms` for navigation alone. Prefer a small range that explains
the point, and return the filename/lines with a short explanation in chat.

The helper keeps file contents, modified buffers, registers and shared-selection
marks intact. It uses existing normal editor windows, preserves Herdr focus,
and clears its own highlights on timeout or edits. It does not create a Visual
selection for MCP to accidentally read. If Insert/Visual mode or a floating
dialog is active, or no normal source window exists, let the user finish first.
On a timeout, inspect the editor before retrying. Reopen/saving/reloading user
buffers is outside this display operation.
