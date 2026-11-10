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

Find Neovim's local Unix sockets under `XDG_RUNTIME_DIR` or its temporary
directory. For each candidate, use the bundled helper without consuming text:

```sh
python3 scripts/read_selection.py --server SOCKET --metadata
```

Match `herdr_pane_id`, `pid` and `cwd` to the editor pane and its
`herdr pane process-info --pane ID` result. Choose the editor in this agent's
tab unless the user specifies another. Resolve ambiguity instead of choosing
the focused window or the newest socket. A `codex_pane_id` field is legacy
linkage metadata, not a requirement to use Codex.

## Read a selection

Use the same native helper in Pi and Codex with the verified editor socket:

```sh
python3 scripts/read_selection.py --server SOCKET
```

This reads the editor's captured selection, including unsaved text. On `ok`,
report the file/range and use the returned text; reuse it for follow-ups because
successful reads consume a capture once. On `no_selection` or `stale`, ask the
user to select the fragment again; on `selection_too_large`, request a smaller
fragment. A timeout may have consumed the capture: report uncertainty rather
than automatically retrying.

Requires the editor's `herdr-codex.context` module, despite its legacy name;
MCP is not required. If unavailable, report the missing editor integration.
The user selects in Visual mode and asks in this chat, by typing or dictation.
For direct sending, the editor's separate `<leader>a` shortcut opens a feedback
card. It can target Pi or Codex: `Ctrl+c` chooses the agent, `Enter` sends, and
`Ctrl+s` stages without submitting. This is distinct from reading a selection
in response to a message in this chat.

## Show a file or range

Use the bundled helper with the verified local socket and an absolute filename:

```sh
python3 scripts/show_file.py --server SOCKET --file /absolute/file.rs --line 24 --end-line 31 --highlight-ms 12000
```

Resolve both helper paths relative to this skill. Pass subprocess argument arrays;
paths and ranges are data, never shell/Lua/Ex code. Line numbers are one-based.
Omit `--highlight-ms` for navigation alone. Prefer a small range that explains
the point, and return the filename/lines with a short explanation in chat.

The helper keeps file contents, modified buffers, registers and shared-selection
marks intact. It uses existing normal editor windows, preserves Herdr focus,
and clears its own highlights on timeout or edits. It does not create a Visual
selection for the reader to accidentally consume. If Insert/Visual mode or a floating
dialog is active, or no normal source window exists, let the user finish first.
On a timeout, inspect the editor before retrying. Reopen/saving/reloading user
buffers is outside this display operation.
