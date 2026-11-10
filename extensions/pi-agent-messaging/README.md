# Pi agent messaging

A small Pi extension for communication between independent interactive sessions. It does not launch agents or manage worktrees; orchestration belongs to the shared `full-agents` skill.

Design and scope: [current guide](../../docs/full-agents.md). Terminology: [glossary](../../GLOSSARY.md).

## Files and requirements

- `extension.mjs`: Pi lifecycle hooks, bounded inbox, linking commands, and `agent_message` tool.
- `messaging.mjs`: private identities, Unix-socket transport, authentication, and acceptance responses.
- `messaging.test.mjs`: real-socket tests and a model-free Pi API test double.
- `fixtures/dialog.mjs`: optional test-only confirmation command; not loaded by the messaging extension.

Requires Unix, Node.js 22.19+ (Pi's runtime minimum) and a Pi version with `ui_prompt_start`, `ui_prompt_end`, `agent_settled`, and custom `followUp` messages. Tested with Node.js 26.13.0; loading/registration was also checked with the installed Pi 1.5.0 loader. No added dependencies or build step.

## Run model-free tests

```sh
cd /home/dev/factory
node --test extensions/pi-agent-messaging/messaging.test.mjs
```

Tests use private temporary directories and real sockets. They cover authentication, linking, wire-size limits, acceptance, unavailable recipients, uncertain delivery, active-receiver collisions, bounded inboxes, dialog deferral, shutdown, and retained identity/link metadata. Pi delivery behavior is exercised through an API test double; this is not an end-to-end interactive test.

## Loading and linking

For the full delegation workflow, use [the full-agents skill](../../skills/full-agents/README.md). Factory's `install-skills` command links this directory into Pi's native user extensions directory; `package.json` declares `extension.mjs` as its entry point. Ordinary Pi startup or `/reload` loads it without a wrapper or settings rewrite. Select the skill explicitly or through `AGENTS.md`. The manual commands below are an alternative for loading messaging without installation or worker orchestration.

Load the extension explicitly in each of two separate interactive Pi sessions:

```sh
pi -e /path/to/factory/extensions/pi-agent-messaging/extension.mjs --name pi-msg-coordinator
```

In the other tab:

```sh
pi -e /path/to/factory/extensions/pi-agent-messaging/extension.mjs --name pi-msg-worker
```

These commands use normal Pi settings and permissions. They neither select a different model nor install the extension globally. Use fresh test sessions rather than opening a second writer on the live coordinator's session file. Loading this extension does not modify an already-running Pi process; continuing an existing conversation with it requires stopping that process and resuming the session with `-e`, after user agreement.

1. Run `/agent-contact` in each participant. It shows the actual session ID and the contact-file path, **not the credential**.
2. In the coordinator, run `/agent-link /absolute/path/to/worker-contact.json`.
3. In the worker, run `/agent-link /absolute/path/to/coordinator-contact.json`.
4. Give each agent the other session's ID and its scoped assignment. Do not paste contact-file contents into prompts.
5. Ask the worker to send a question using `agent_message` with the coordinator ID as `recipient`. Have the coordinator reply with the same tool; then have the worker report its result.
6. Demonstrate a message arriving after the coordinator finishes, and another arriving while the recipient is busy. The user must remain able to converse directly in both tabs.

The tool takes only `recipient` and `content`; it looks up credentials privately. A slash command links peers; an incoming message cannot create links. Registration, question, and ready reports are assignment conventions, not automatic transport events. Neither agent should send empty acknowledgments or retry an unconfirmed send automatically.

## Optional live dialog fixture

Explicitly load `fixtures/dialog.mjs` as a second extension in a dedicated test session, alongside `extension.mjs`. Run `/messaging-test-dialog` there, then send it a message from a linked peer while the confirmation is open. The dialog takes no action for either answer and automatically cancels after 30 seconds.

The fixture records `opened` and `closed` session entries, including the returned confirmation result. Compare these with the sender's acceptance time and the recipient's custom agent-event entry. The live test confirmed acceptance during the dialog and delivery only after it closed with `confirmed: false`. Do not infer dialog state solely from Herdr's agent status: it did not report `blocked` for this dialog in the installed version.

## Delivery semantics

- One authenticated JSON frame per connection. The complete UTF-8 frame, including credential and terminating newline, must fit in **16 KiB**.
- A receiver admits at most **32 pending messages**, including a message handed to Pi until its `message_start` event is observed.
- Messages wait in extension memory while Pi is busy or an extension UI dialog is open. Event hooks, not polling, resume delivery. One message at a time is handed to Pi using `{ deliverAs: "followUp", triggerTurn: true }` when it is idle.
- Incoming content is a visible custom `agent-event`, not a user message. Its wrapper explicitly says that it is delegated communication, not human authorization.
- Dialog deferral observes Pi's extension UI events (`select`, `confirm`, `input`, `editor`, `custom`). A natural-language question in chat is not an open UI dialog; the extension cannot infer that the user intends the agent to remain paused. Assignment instructions still govern human checkpoints.
- Acceptance means validation and admission into volatile memory, **not reading, a model response, persistence, or task completion**. Pi can still reject a subsequent run or encounter a provider failure; its normal runtime error reporting applies.
- After **5 seconds** without a valid acceptance reply, delivery is **unconfirmed**. The receiver may already have accepted the message. Cancellation after connection is also uncertain. There are no automatic retries, duplicate suppression, or exactly-once guarantees.
- Queue overflow, invalid credentials/envelopes, and unlinked senders are rejected. Tool errors do not echo arbitrary peer-supplied response text or credentials.

## Identity and lifecycle

The runtime directory defaults to `$XDG_RUNTIME_DIR/pi-agent-messaging-UID`, or the same directory name under the OS temporary directory when `XDG_RUNTIME_DIR` is absent. Override with `--agent-messaging-dir /short/private/path` in both participants if necessary. It must be user-owned with no group/other permissions, and short enough for Unix socket paths.

Each actual Pi session ID gets a deterministic socket path and a private contact file containing its random receiver credential and linked peer contacts. This metadata survives a normal stop, `/reload`, and resuming the same session **while the directory remains available**. Pending messages do not survive. `/new` and `/fork` use their new session IDs, with separate addresses, credentials, and no inherited links.

`session_shutdown` closes connections, stops the receiver, and drops pending messages. A worker remains independent when the coordinator closes; subsequent sends report the unavailable recipient. Restoring a session allows fresh sends, not recovery of previously failed ones.

Starting two receivers for the same session is refused. Startup never unlinks an existing socket. After an ungraceful crash, a stale socket may require manual removal; first verify that no process is using that exact session/socket. Do not delete a live receiver's socket. Automatic stale-socket recovery is intentionally absent.

## Trust and limitations

Contact files are private (0600); the runtime directory is private (0700). Each receiver requires its random credential and an explicitly linked sender session ID. Credentials never enter tool arguments, message content, or tool results through this extension.

This protects against accidental connections and other OS users, **not malicious processes running as the same OS user**. Such processes may read or modify credentials and impersonate linked agents. This extension is not a sandbox or an approval-enforcement system. Messages and assignment instructions cannot grant authority beyond the user's scope.

Live Pi checks demonstrated the round trip, idle wake-up, busy-recipient and dialog deferral, reload, graceful close/resume without relinking, and new/fork routing isolation. The installed shared skill also completed repository-worker trials. See [the validation summary](../../docs/full-agents.md#validation-and-limits) and [detailed historical evidence](../../docs/pi-agents-prototype.md#delivery-2-live-test-evidence).

Copied assignment text in a fork is not rewritten automatically; its actual transport identity and links are independent. This Pi transport does not provide a Codex bridge, automatic peer discovery, a daemon, persistent message queue, automatic retry or session cleanup. Native extension auto-discovery is installation behavior, not automatic linking between agents.
