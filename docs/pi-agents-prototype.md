# Interactive agents: implementation history

> Archived development record. Sections below are chronological; later decisions
> superseded earlier prototype restrictions and paths. Use [the current guide](full-agents.md)
> for supported pairings, installation and validation. This history is not an
> active task plan or a source of new authorization.

## Status and authorization

Design agreed through an interview with the user. The user authorized Delivery 1 and then explicitly requested the interactive test. Delivery 1 is implemented. Live checks have demonstrated the Pi ↔ Pi round trip, idle wake-up, busy-recipient deferral, worker `/reload` continuity, extension UI dialog deferral, graceful close/resume behavior, and identity isolation on `/new` and `/fork`.

The user requested small, reviewable steps. The latest authorization promotes the
shared workflow to normal installation and retires `codex-full-agents`; earlier
restrictions below are historical and superseded only within this new scope.

The user subsequently authorized integration with Factory's installer. Canonical
sources now live in `skills/full-agents/` and `extensions/pi-agent-messaging/`;
the former `experiments/` paths remain compatibility symlinks for live sessions.
Earlier delivery notes below retain their historical experimental paths. See the
normal-installation section for the current setup, live checks and blockers.

The user authorized tracking the prototype on `work/full-agents` in the existing `/home/dev/factory` checkout, without another worktree. The branch was created from `f15eb759fb7925ddd412204892eedb2cce9b31ea`, preserving the unrelated commits already on `main`. The user subsequently authorized a local checkpoint commit of the prototype on this branch; publication is not authorized. The separate worker test edit remains uncommitted on `work/skill-smoke-pi` and has not been integrated here. All agents sharing the original checkout see its current branch.

Terminology: [glossary](../GLOSSARY.md).

## Goal

Reproduce in Pi the experience of delegating to independent interactive agents in Herdr tabs: the user can speak directly to each worker, and the coordinator receives their messages automatically, even after finishing its response.

The eventual goal is a shared skill that supports choosing Pi or Codex workers without changing the coordinator's harness. Ask for this choice only when neither the request nor an explicit preference specifies it. Choosing the agent harness does not determine its model.

First validate only a Pi coordinator ↔ one Pi worker. Unification with Codex comes later.

## Verified facts

- The installed Herdr supports `herdr agent start ... --kind pi`.
- Pi supports explicitly loading extensions with `-e`.
- Extensions can register tools and deliver custom messages through `pi.sendMessage`.
- `deliverAs: "followUp"` allows delivery after the current work finishes; `triggerTurn: true` allows starting a turn when the recipient is idle.
- Extension resources must be opened in `session_start` and closed in `session_shutdown`, not during the factory.
- `/home/dev/factory` contains the existing skill; its worktree was clean when inspected.
- `/home/dev/test-pi` was empty and was not a Git repository.

These facts establish mechanism availability, not an end-to-end demonstration of agent communication.

## Agreed decisions

1. Keep agents as full interactive sessions, not hidden subagents or ephemeral jobs.
2. The worker remains available if the coordinator finishes or closes.
3. Implement the prototype in isolation within `/home/dev/factory`, without modifying `skills/codex-full-agents`.
4. Use a Pi extension explicitly loaded in each participant, without global installation.
5. Use one Unix socket per participating session in a user-private directory. No network ports or central service.
6. Include the recipient address explicitly in the assignment; do not build global discovery.
7. Provide a small tool, provisionally named `agent_message`, for sending messages from either agent.
8. Display messages as agent events, never as user instructions or approvals.
9. Use `followUp`: messages wait while the recipient is working and can start a turn when it is idle.
10. Distinguish acceptance, reading, and completion. The transport response confirms only acceptance or an error.
11. Report delivery failures without persistence or automatic retries. Do not guarantee delivery to closed sessions.
12. Apply Matt Pocock's skills from their existing files. Discovery or installation in Pi is a separate task.
13. Bind the receiving address to the conversation: preserve it on `/reload` and when resuming the same session; use a different address on `/new` or `/fork`. Messages addressed to an inactive old conversation must fail rather than reach the new one. Resuming the old session allows new sends once its receiver is available; previously failed sends are not recovered.
14. Accept messages only from explicitly linked participants using a random credential per receiver in addition to its address. Give each participant only the contact details it needs. This prevents accidental connections, not malicious access by processes running under the same operating-system user.
15. Hold agent messages while a user question or approval dialog is open. Do not close, answer, or approve the dialog. Once it closes, apply normal `followUp` delivery; agent messages cannot override a human rejection.
16. Use text messages with a minimal envelope: protocol version, message ID, sender session, recipient session, and content. Authenticate separately; never include the credential in model-visible content. No attachments or rigid event taxonomy: `registered`, `question`, and `ready` remain assignment conventions.
17. Limit each complete message to 16 KiB and each receiver to 32 pending messages. Reject new messages when full. Allow 5 seconds for acceptance confirmation, sent only after validation and admission into memory. Closing the process may lose accepted pending messages. A timeout means delivery is unconfirmed, not necessarily that delivery failed. Do not retry automatically.
18. Put the extension, tests, and README in `experiments/pi-agent-messaging/`, separate from stable tooling and the existing skill. Keep this plan in `docs/`. Document and verify the concrete two-session loading procedure before executing it.

## Delivery 1: minimal reviewable component

Contents:

- Extension with a local receiver, sending through `agent_message`, and resource cleanup.
- Tests of the transport and its integration with Pi's API without model calls.
- Brief instructions for loading and verifying the extension.

Prioritize a small implementation without unnecessary external dependencies. If new requirements expand the scope, stop and discuss them before adding them.

Before implementation: resolve the open design questions, present the updated summary, and obtain user confirmation.

After implementation: present files, change size, test results, and limitations. Wait for review before opening agents.

## Delivery 2: interactive test, after review

Prepare two participating Pi sessions in Herdr, with the worker in another tab. Preserve the user's ability to speak directly to both.

Use a harmless assignment: no repository changes or writes to external services.

Test sequence:

1. The coordinator provides an assignment and a return address.
2. The worker registers and sends a question.
3. The coordinator receives the event and replies to the worker.
4. The worker receives the reply and reports the result.
5. At least one event arrives after the coordinator has finished its response and triggers a new turn without user intervention.

If the current coordinator session cannot load the extension directly, explain the required procedure before reloading or opening another session.

## Acceptance criteria

### Delivery 1

- Local sending and receiving without polling terminals or files.
- Messages identified as communication between agents.
- `followUp` delivery configuration and activation while idle verifiable without a model.
- Clear errors for unavailable recipients.
- Acceptance confirmation without claiming reading or completion.
- Resources closed when the session ends or is replaced, according to the lifecycle contract still to be defined.
- Nothing installed globally and no changes to the existing Codex skill.

### Delivery 2

- Full coordinator → worker → coordinator circuit and subsequent reply.
- Automatic activation of an idle recipient demonstrated with real sessions.
- A message to a busy recipient waits without interrupting its work.
- Both sessions remain interactive, and the worker does not depend on the coordinator staying open.
- No delegated event is interpreted as human approval.

## Out of scope for now

- Codex messaging compatibility and a sending CLI command.
- Unified skill and Pi/Codex preference configuration.
- Automation of multiple workers, worktrees, tabs, or editors.
- Integrations with issues, PRs, or external services.
- Persistent queues, automatic retries, a crash monitor, or a central service.
- Global extension or skill installation.
- Commits, publication, integration, or automatic session cleanup.

## Delivery 1 review evidence

The original files were in `experiments/pi-agent-messaging/`; their current
location is [`extensions/pi-agent-messaging/`](../extensions/pi-agent-messaging/README.md):

- `extension.mjs`: lifecycle hooks, bounded inbox, linking commands, and sending tool (122 lines).
- `messaging.mjs`: private contact metadata and socket transport (177 lines).
- `messaging.test.mjs`: 10 model-free tests (269 lines).
- `README.md`: loading/linking instructions, semantics, and limitations (78 lines).

Checks performed:

- `node --check` on both implementation files.
- `node --test experiments/pi-agent-messaging/messaging.test.mjs`: 10 passed.
- Installed Pi 1.5.0 extension loader: successfully registered the extension, tool, commands, and lifecycle handlers without starting sessions or model calls.

Transport tests use real Unix sockets. Pi-facing Delivery 1 tests use an API test double; live checks are recorded separately below. No dependencies were added, no global configuration was changed, and no agents were launched during Delivery 1.

The extension keeps accepted messages in its own bounded memory inbox until Pi is idle and no extension UI dialog is open. It then hands one message at a time to Pi using `followUp`, counting it as pending until its custom `message_start` is observed. Identity/link metadata, but not pending messages, is retained in private runtime files.

Dialog deferral covers Pi extension UI events. A natural-language question in chat is not an open UI dialog; the extension cannot infer an intended human checkpoint from text. Such checkpoints still require assignment instructions. This limitation must remain explicit in the interactive test.

## Delivery 2: live test evidence

The user explicitly requested the live test after the Delivery 1 report. Two interactive Pi 1.5.0 sessions were started in Herdr workspace `w2`, using the configured implementer model `openai/gpt-6.1-sol` with high reasoning. No global settings or implementation files were changed for the test.

| Role | Herdr tab / pane | Actual Pi session ID |
| --- | --- | --- |
| Test coordinator | `pi-msg-coordinator` / `w2:p3` (`w2:t2`) | `01a1c19e-86fa-71b5-9ca7-d2fa9bfd5bdf` |
| Worker | `pi-msg-worker` / `w2:p4` (`w2:t3`) | `01a1c19e-86fc-73f9-8104-37d72e732ee0` |

Both use `/home/dev/factory` with no task-related repository writes or external service writes authorized. No worktrees were created for this harmless messaging test. The invoking conversation has no messaging extension loaded, so a separate test coordinator was used rather than restarting it.

Runtime identity/link metadata is in `/tmp/pi-msg-live.7w9J4f`. Do not copy its credentials into prompts or documents. Both sessions were explicitly linked in both directions and remain available for direct user conversation. Cleanup was not performed.

Verified sequence:

1. Coordinator finished its initial response at `2026-11-09T18:44:05.930Z`.
2. Worker sent its registration/question, delivered as a custom agent event at `18:44:22.593Z`; this activated the idle coordinator without further user input.
3. Coordinator sent `COORDINATOR_REPLY request=q1 answer=4` through `agent_message`.
4. Worker received the reply and sent `WORKER_EVENT kind=ready`; the coordinator summarized the completed round trip. No empty ACK loop occurred.
5. For the busy-recipient check, the coordinator ran a harmless 25-second wait. The worker's probe was accepted at `18:45:22.323Z`, while the coordinator's tool was still running (tool result at `18:45:37.896Z`).
6. Coordinator completed its current response, `BUSY_TURN_FINISHED`, at `18:45:40.428Z`. The queued probe appeared as a custom event at `18:45:40.434Z`, followed by `BUSY_PROBE_RECEIVED_AFTER_TURN`. It did not interrupt the active run.

Evidence is retained in the named sessions. In `/home/dev/.pi/agent/sessions/--home-dev-factory--/`, their files are `2026-11-09T18-42-34-364Z_01a1c19e-86fa-71b5-9ca7-d2fa9bfd5bdf.jsonl` and `2026-11-09T18-42-34-366Z_01a1c19e-86fc-73f9-8104-37d72e732ee0.jsonl`.

### Worker reload continuity

After the user requested continuing with the experiment, `/reload` was run in the existing worker tab, without closing the process or changing its assignment scope. Pi reported that extensions and other resources were reloaded.

The worker retained the same actual session ID, socket path, receiver credential, and linked coordinator metadata (compared privately before/after, without exposing credentials). No linking command was rerun. The coordinator then sent `RELOAD_PROBE request=q3`; the reloaded worker received it and sent `RELOAD_REPLY request=q3` to the coordinator. Both messages were accepted and delivered as custom agent events, and the coordinator reported the successful round trip.

Implementation files and global settings were unchanged; both sessions remain available.

### Extension UI dialog deferral

A test-only fixture was added at `experiments/pi-agent-messaging/fixtures/dialog.mjs` (16 lines), plus a model-free test. The main extension and transport were unchanged. The suite now has 11 passing tests.

To avoid restarting the existing participants or altering their explicit extension lists, a separate interactive Pi receiver was opened in tab `pi-msg-dialog`, pane `w2:p5` (`w2:t4`), with actual session ID `01a1c1d9-03b7-74aa-9665-d9b35bb2b4f5`. It explicitly loads the main extension and the fixture and is linked to the coordinator in both directions. It remains open for user inspection.

The fixture's `/messaging-test-dialog` command opens a harmless confirmation with a 30-second auto-cancel. Neither answer authorizes an operation. Recorded sequence on `2026-11-09`:

1. Dialog opened at `19:47:17.745Z`.
2. Coordinator's `DIALOG_PROBE request=q4` was accepted at `19:47:31.739Z`, while the dialog remained open. A terminal snapshot still showed the confirmation and no delivered event.
3. Dialog closed at `19:47:47.785Z` with `confirmed: false`; no affirmative input was sent.
4. The queued custom agent event was delivered at `19:47:47.794Z`.
5. Receiver replied `DIALOG_PROBE_DELIVERED_AFTER_DIALOG` and ended its turn.

Evidence is in the existing coordinator session and `2026-11-09T19-46-27-384Z_01a1c1d9-03b7-74aa-9665-d9b35bb2b4f5.jsonl` in the same Pi session directory. The fixture's `opened`/`closed` entries are test instrumentation and do not enter model context.

Observability caveat: Herdr did not expose this Pi confirmation as agent status `blocked`; a wait for that status timed out even though the dialog was visible. Message deferral correctly uses Pi's own UI lifecycle events rather than Herdr status. No Herdr changes were made.

### Closed recipient and resuming the same session

The user explicitly authorized temporarily closing `pi-msg-worker` and resuming that same session. After a scoped preparation instruction, Ctrl+D exited Pi gracefully in pane `w2:p4`; the foreground process returned to its shell and the worker socket was removed. Its private identity/link metadata remained on disk.

Recorded sequence on `2026-11-09`:

1. Coordinator attempted exactly one `CLOSED_PROBE request=q5-closed` while the worker was stopped. At `19:51:27.464Z`, the tool returned `Recipient unavailable; connection failed before sending.` with `isError: true` (2 ms tool duration). No retry was issued.
2. The worker was restarted in the same pane using `--session` with its original JSONL file, the same explicit extension, and the same runtime directory. The session ID, socket path, credential, and linked coordinator were unchanged. No relinking was performed.
3. Coordinator sent a fresh `RESUME_PROBE request=q5`, accepted at `19:52:05.756Z` and delivered in the original worker conversation at `19:52:05.777Z`.
4. The resumed worker sent `RESUME_REPLY request=q5`, delivered to the coordinator at `19:52:11.599Z`. The coordinator reported the successful round trip.
5. The failed closed-recipient probe was neither replayed nor delivered after resume. Both original participant sessions remain open, along with the separate dialog test session.

The implementation and global settings were unchanged. Evidence is in the same coordinator and worker session files recorded above. This tests graceful shutdown, not recovery from a crash or lost runtime directory.

### Isolation on `/new` and `/fork`

Following the user's request to continue, native Pi session commands were exercised in auxiliary pane `w2:p5`; the coordinator and implementer sessions were left running unchanged. No additional fixture code was needed.

- `/new` replaced the auxiliary parent conversation with session `01a1c1e1-da6f-74aa-9665-d9b51d98491f`, which had a separate socket and no linked peers. The parent's socket was closed. A single coordinator send to the old parent ID failed before sending at `2026-11-09T19:56:29.363Z`. The new conversation remained empty and was not activated by the old-address probe.
- The original auxiliary conversation was restored using `/resume`, selecting its verified session file.
- Native `/fork` then created session `01a1c1e3-466b-74aa-9665-d9b63ba120dc` from the original conversation's user-message checkpoint. It had a different identity, credential, and socket, with no inherited links. The restored draft was cleared without submission. A single coordinator send to the old parent ID failed before sending at `19:58:04.190Z`; the fork received no event and made no model call.
- Finally, `/resume` restored the original auxiliary session `01a1c1d9-03b7-74aa-9665-d9b35bb2b4f5`. Its original socket reopened, and both temporary child sockets closed. Contact metadata was retained; no cleanup or relinking was performed.

These checks validate routing isolation, not automatic rewriting of copied assignment text. A fork may contain historical instructions naming its parent; the transport still uses the actual session ID and does not inherit parent links.

The main extension and transport remained unchanged. All originally planned basic live scenarios have now been exercised. Crash recovery, load testing, and cross-harness messaging remain outside the validated scope. Direct user interaction in each tab is available but was not simulated on the user's behalf.

## Continuation

Keep the implementation under `experiments/` during validation. Once promoted out of experiment status, the agreed organizational direction is a Pi-specific extension under `extensions/pi-agent-messaging/` and a separate shared coordination skill under `skills/`; Codex and other harnesses need their own adapters. Do not move files as part of the current test.

## Experimental full-agents skill

After discussing the next step, the user explicitly authorized preparing the shared `full-agents` skill as an experiment, using `codex-full-agents` as its base rather than adding a separate Pi-only workflow.

The documentation-only draft was at `experiments/full-agents/`; its current
location is [`skills/full-agents/`](../skills/full-agents/README.md):

- `SKILL.md`: shared harness selection, assignment, launch, coordination, and review instructions.
- `references/herdr.md`: shared branch/worktree, tab, optional editor, and resume procedure.
- `references/pi.md`: explicit extension preflight, startup, private bidirectional linking, messaging, and lifecycle limits.
- `references/codex.md`: existing interactive Codex startup and native queue mechanism.
- `references/worker.md`: shared registration, event conventions, collaboration, and human authorization contract.
- `README.md`: current support, explicit loading, and experimental status.

The draft asks for the worker harness unless already chosen explicitly. Pi and Codex are separate from model selection. Pi ↔ Pi uses the validated extension; Codex ↔ Codex retains the legacy mechanism but has not been newly tested through this generalized skill. Mixed-harness pairings and other harnesses are blocked before creating worktrees or tabs; no return bridge or external Pi messaging client has been implemented.

Validation: Pi 1.5.0's skill loader recognizes `full-agents` without diagnostics; relative file references and whitespace were checked. The messaging suite still has 11 passing tests. No launch script, helper, dependency, global installation, installed-skill replacement, or new agent session was introduced for this step. The existing `skills/codex-full-agents`, `skills.yaml`, and setup script remain unchanged.

## Experimental skill: repository-worker trial

The user authorized an end-to-end skill trial. The existing extension-enabled Pi test coordinator read `experiments/full-agents/SKILL.md` and the shared Herdr, Pi, and worker references, then followed them to launch one interactive Pi implementer for a scoped read-only repository task. The invoking conversation was not restarted or replaced.

Retained participant:

- Name/tab: `skill-smoke-pi`, tab `w2:t5`.
- Worker pane: `w2:p6`; configured Neovim/LazyGit editor pane: `w2:p7`.
- Actual Pi session ID: `01a1c1f2-840b-7541-ae81-b79e6643b484`.
- Worktree: `/home/dev/.local/share/factory/worktrees/nachfq/factory/skill-smoke-pi`.
- Branch: `work/skill-smoke-pi`.
- Base and final HEAD: `c843fbf96e065b2fbae14c40ff127bde18ac4319`.
- Model: `openai/gpt-6.1-sol`, high reasoning; Pi's existing permission policy retained, without Codex bypass flags.

Assignment: inspect tracked `README.md`, `docs/skills.md`, and installer entry points only as needed; return three findings about Factory skill installation/default contents, with file/line references and clean-worktree checks. No installation, source changes, commits, publication, extra agents, or cleanup was permitted.

Verified sequence:

1. Coordinator checked configuration, storage, repository/base, actual pane/workspace, and its messaging receiver before creating a separate branch/worktree and worker tab. The optional configured editor was opened alongside the worker.
2. Worker loaded the experimental skill and messaging extension through absolute original-checkout paths, since the experiments are not tracked at the base and are absent from its new worktree. Task evidence came from tracked worktree files, not the original uncommitted docs.
3. Coordinator established and verified both links before dispatching the assignment once.
4. Worker verified its actual ID, directory, branch/base, and clean status, then sent `registered` through `agent_message`, received by the coordinator at `2026-11-09T20:15:24.855Z`.
5. Worker completed the read-only inspection and sent `ready`, received at `20:16:14.583Z`.
6. Coordinator read the cited sources and independently verified the worktree/base before reporting success. The invoking session also checked the findings against tracked documentation, confirmed branch/HEAD, empty `git status --porcelain=v1 --untracked-files=all`, a zero exit from the full base diff, and the retained editor process.

The result correctly identified `setup-agent.sh install-skills`, the own-skill links and pinned Codex plugin bundle, and excluded/separate components. No source edits or installation occurred. The experimental skill and extension remain uninstalled; the existing skill is unchanged. Worker, editor, branch, and worktree remain available for direct human review.

Evidence: coordinator session recorded above; worker session file `/home/dev/.pi/agent/sessions/--home-dev-.local-share-factory-worktrees-nachfq-factory-skill-smoke-pi--/2026-11-09T20-14-18-638Z_01a1c1f2-840b-7541-ae81-b79e6643b484.jsonl`.

This initial trial validates the documented Pi repository-worker launch/delegation flow for read-only work. The later bounded test-edit trial is recorded below; multi-worker coordination, mixed harnesses, and promotion/installation remain outside this validation.

## Bounded edit trial: human checkpoint and completion

After the user requested continuing the Pi work (with Codex validation deferred), a candidate edit trial was proposed: add one regression test in the existing worker worktree's `scripts/tests/test_install_skills.py`, covering byte-for-byte preservation of existing Factory preferences over conflicting legacy preferences. Production behavior was already implemented; no production change was requested. Checks would use the existing temporary-HOME/local-Git fixture and exclude native Codex/plugin tests.

The coordinator verified the same worker identity and clean worktree and sent this bounded follow-up through `agent_message`. The worker received it, but paused before edits: its original direct assignment explicitly prohibited all edits, and it did not accept a delegated assertion of new human permission as overriding that limit. It sent `kind=question request=preferences-test` asking for direct human authorization of the designated edit/checks. The coordinator surfaced the checkpoint without retrying or bypassing it.

At that checkpoint, no test had been added or run and the worktree remained clean. The user then answered `ok` directly in the worker tab and confirmed that approval in the invoking conversation. No delegated message or fabricated approval was used to bypass the checkpoint.

The same worker subsequently added exactly one test, `test_existing_factory_preferences_are_preserved_over_legacy`, at `scripts/tests/test_install_skills.py:159`: 16 inserted lines and no deletions. It seeds conflicting Factory/legacy settings, including an unrelated Factory key and distinct formatting, then verifies that both files remain byte-for-byte unchanged after the fixture installer runs. This covers existing behavior, not a production bug fix.

Worker, test coordinator, and invoking session independently verified the result:

- New test alone: 1 passed, no skips.
- All `InstallSkillsTest` methods whose names exclude `native`: 10 passed, no skips; the new test is included in those 10. The two native/plugin cases were excluded without changing test code.
- `git diff --check`: passed.
- Branch remains `work/skill-smoke-pi`; HEAD remains `c843fbf96e065b2fbae14c40ff127bde18ac4319`.
- Only worker-worktree modification: `scripts/tests/test_install_skills.py`, +16/-0. No other tracked or untracked worker files changed.

Reproduction from the worker worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s scripts/tests -p test_install_skills.py \
  -k test_existing_factory_preferences_are_preserved_over_legacy -v
```

The 10-case batch selects `unittest.defaultTestLoader.getTestCaseNames(InstallSkillsTest)` excluding names containing `native`, then runs a `unittest.TestSuite` of those cases. Checks use temporary HOME/local Git fixtures, not live installation or real user configuration. Fixture-internal Git commits belong to the existing tests; no commit was made in either Factory worktree. No Codex worker or native/plugin test was run.

The worker reported ready through `agent_message`, and the coordinator reviewed the actual diff and reran checks. The invoking session also read the edited test and independently reran both selections. The test edit remains uncommitted in the worker branch; it was not copied or integrated into the original checkout. Evidence remains in the existing worker/coordinator sessions.

This validates a bounded test-file edit/check/review cycle and a real human authorization checkpoint. It does not validate production behavior changes or cross-harness operation.

## Installer integration

After the local prototype checkpoint (`5626b53`), the user authorized integrating
the validated Pi workflow with the existing installer, without replacing
`codex-full-agents` or automatically changing global configuration.

- Moved canonical sources to `skills/full-agents/` and
  `extensions/pi-agent-messaging/`; no messaging implementation changes.
- Kept `experiments/full-agents` and `experiments/pi-agent-messaging` as relative
  compatibility symlinks, preserving existing session arguments and read-only
  assignment paths. No sessions or worktrees were removed or restarted.
- Updated the Pi adapter to resolve the skill's canonical location before deriving
  the extension path, including when the skill is installed via a symlink.
- The existing installer discovers `full-agents` as an ordinary own skill, using
  its existing preflight, conflict handling, managed links and replacement backups.
  No additional command or global Pi configuration is installed.
- At user request, removed a proposed convenience wrapper and its tests before
  commit. The entry point is the skill; `AGENTS.md` can make its selection a
  standing instruction. Skill instructions do not load executable extensions;
  messaging is enabled through Pi's native settings or explicit `-e` option.
- The default bundle's native Codex plugin dependency remains unchanged; Pi must
  be installed separately. Installing the skill does not start Pi.

Validation uses isolated temporary homes and local Git fixtures, not a live user
installation:

- Nine non-native installer tests passed, including dry-run reporting/no writes,
  coexistence with `codex-full-agents`, no Pi settings creation, and reinstall
  idempotence. The separate worker's preservation test was not integrated here.
- Wider script suite: 28 selected, 27 passed, one existing Incus/SSH integration
  test skipped because laptop homelab access is required. Two native/plugin
  cases were excluded; no Codex worker validation was performed.
- All 11 model-free messaging tests passed from the new canonical location.
- The installed Pi 1.5.0 loader loaded both extension paths and deduplicated
  installed/canonical/compatibility skill paths without diagnostics. No session,
  model turn or receiver was started for this check.

After explicit installation, invoke the skill or select it through `AGENTS.md`.
For Pi messaging, load the extension through native settings or `-e`; the
installer does not configure this automatically. Resuming requires explicit
`--session` and first stopping any process writing that exact conversation. See [the skill guide](../skills/full-agents/README.md)
and [bundle installation](skills.md).

## Normal installation and image parity

The user subsequently clarified that this is no longer an experiment, authorized
retiring `codex-full-agents`, and requested installation in this environment using
the same path as a newly instantiated image, followed by live tests. This
supersedes the earlier restrictions on installing the shared workflow here.
It does not authorize publishing images, pushing commits, unrelated configuration
changes, session cleanup, or claiming mixed-harness support before implementation.

- `full-agents` is now the only full-agent skill in Factory. Removed the old
  skill's three source files. The installer retires its previous managed symlink
  through the existing ledger; it does not remove unrelated skills.
- Added a native Pi extension manifest and a managed link under
  `${PI_CODING_AGENT_DIR:-~/.pi/agent}/extensions/pi-agent-messaging`. Ordinary Pi
  startup or `/reload` discovers it; no wrapper or settings rewrite is needed.
- Added `setup-agent.sh install-pi` using Pi's official installer and included it
  in the image recipe/tool checks. Image preparation also refuses a Pi auth file,
  just as it refuses Codex/GitHub credentials. No image was built or published.
- Pi 1.5.0 and Codex 0.167.0 were already installed in this environment, so their
  binaries were not unnecessarily reinstalled or updated during live tests.
- Ran the real `install-skills --dry-run`, then `install-skills` twice. The first
  run linked the shared skill and native extension and retired the old skill;
  the second kept matching links. Snapshots verified that existing Pi settings
  and auth, Codex config and auth, and Factory worker preferences were unchanged.
- All 34 script tests ran, including native Codex plugin fixture cases: 33 passed
  and the existing homelab-dependent Incus/SSH test was skipped. All 11 messaging
  tests passed. Shell syntax checks passed for setup and the image recipe.

### Installed Pi live trial

Started a normal interactive `pi --name installed-pi` in `w2:t7` / `w2:p9`, with
no explicit skill or extension flags. Startup listed `full-agents`, `herdr-nvim`,
and `sidequestion`, but not the retired skill, and discovered `extension.mjs`.
`/agent-contact` worked. Actual coordinator session:
`01a1c24b-486a-740d-a021-f2e29ef73e86`.

That test coordinator followed the installed skill to create one read-only worker
`installed-pi-worker` (`w2:t9` / `w2:pB`), actual session
`01a1c24c-fba4-77cd-9e8f-6d7c167a476d`, on branch
`work/installed-pi-worker` in
`/home/dev/.local/share/factory/worktrees/nachfq/factory/installed-pi-worker`.
Base/HEAD: `5626b539b492164eaab79de6919fa5bff5ceb491`. The installed canonical
resources in the original checkout were explicit read-only inputs because the
installation changes were not yet committed into that base.

Registration, a worker question asking which installed directory to inspect,
one coordinator reply, and the worker's three findings plus ready all flowed via
`agent_message`. The worker verified the installed skill link and native manifest
entry `./extension.mjs`. The test coordinator and invoking session independently
verified its clean worktree and unchanged base. No worker file edits, installs,
commits or cleanup occurred. The invoking conversation/model was not replaced;
these were visible auxiliary test sessions, preserved for direct user inspection.

### Installed Codex live trial

Started normal interactive Codex in `installed-codex`, tab `w2:t8`, pane `w2:pA`.
It initially paused at browser authentication. No task was dispatched until the
user completed that login and confirmed it in the invoking conversation. No Pi
credentials were copied and no alternate provider was silently selected.

The installed shared skill then completed the bounded Codex↔Codex trial:

- Coordinator thread: `01a1c2b8-10a1-7e42-bf29-92a4ff2c62da`, saved name
  `installed-codex`, tab/pane `w2:t8` / `w2:pA`.
- Worker thread: `01a1c2b9-d9a4-7972-a039-7b9458173015`, saved name
  `installed-codex-worker`, tab/pane `w2:tA` / `w2:pC`.
- Exactly one agent-only worker, using configured `gpt-6.1-sol`, high reasoning
  and existing configured bypass permissions. No coordinator settings or user
  focus were changed by commands in the trial.
- Worktree:
  `/home/dev/.local/share/factory/worktrees/nachfq/factory/installed-codex-worker`;
  branch `work/installed-codex-worker`, base/HEAD
  `5626b539b492164eaab79de6919fa5bff5ceb491`.
- The actual worker UUID was verified, its conversation was named, and its
  assignment supplied the installed shared worker contract and Codex adapter.
  Original-checkout installed resources were explicit read-only inputs because
  the installation changes were not committed into the worker base.

Registration and a directory-inspection question arrived as actual native queued
messages after coordinator turns yielded. The coordinator sent one reply with
`codex queue`, naming the installed skill path and expected canonical target.
That queued reply activated the worker; its subsequent queued ready report
confirmed processing. There was no transcript polling, empty ACK exchange,
uncertain-send retry or Herdr-prompt substitute for inter-agent messaging.

The worker reported the installed skill symlink/target, the supported same-harness
and blocked mixed pairings, and clean branch/base/status. The test coordinator and
invoking session independently verified its clean worktree and unchanged base.
No source edits, installation, commits, integration or cleanup occurred in the
trial. Both Codex sessions remain available for direct user conversation.

This validates the installed shared skill on Codex↔Codex and Pi↔Pi independently.
It does not validate Pi↔Codex: that bridge remains unimplemented.

## Promotion checkpoint

The user authorized repository cleanup and a local commit after both installed
same-harness trials passed. Current usage and validation are consolidated in
`docs/full-agents.md`. The old `experiments/` symlinks remain local and ignored,
not versioned, so preserved sessions retain their historical resource paths.
No session or worktree cleanup is included. The separate worker's 16-line test
remains unintegrated; Pi↔Codex transport remains unimplemented. No push or image
publication is part of this checkpoint.
