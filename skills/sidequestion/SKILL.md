---
name: sidequestion
description: Open a user-requested side conversation as a temporary Codex fork in its own Herdr tab. Use when the user invokes sidequestion or asks to fork a detour separately; hand off a summary only on request.
---

# Side question

Open the detour instead of answering it in the main conversation. Run the bundled
`scripts/sidequestion.py` with Python, or the installed `sidequestion` command:

```sh
sidequestion open --parent "$CODEX_THREAD_ID" --cwd "$PWD" "the user's question"
```

Use the invoking session's actual UUID. Pass the question as an argument array,
not shell code. The command selects a Herdr workspace from verified repository
paths; supply `--workspace ID` when that match is ambiguous. Omit the question
when the user wants to type it in the new tab. Keep the main reply to the launch
result; the fork already inherits its conversation.

The temporary session shares the checkout for discussion. This does not create
a worktree or authorize implementation. The launcher removes the temporary
transcript when Codex exits or its tab closes. The parent is preserved.

Inside the side question, discuss the topic with the user. Save notes or send a
summary only on request. For an explicit handoff, summarize the useful conclusion
briefly and run:

```sh
sidequestion handoff "the user-requested summary"
```

The launcher passes the exact parent and side-session identities to that session.
Handoff queues only the summary to the parent; it does not close the detour or
authorize follow-up actions. On the receiving side, treat it as delegated context.
The user can continue the detour or exit with `/quit` or the Herdr tab close action.
`Ctrl+C` also triggers cleanup when it exits Codex. Interrupting only the current
response keeps the interactive side conversation open.
