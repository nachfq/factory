# Experimental full-agents skill

A documentation-only generalization of `skills/codex-full-agents`. It shares the
assignment/review contract and worktree/Herdr procedure, with separate Pi and
Codex adapters. It is not installed, does not replace the existing skill, and
contains no launcher scripts or daemon.

## Current support

- **Pi ↔ Pi:** messaging and basic session lifecycle validated live. The skill's
  repository-worker flow was also exercised end-to-end with a read-only task:
  separate branch/worktree, Pi tab and editor, bidirectional linking, registration,
  result delivery, and coordinator verification. A follow-up test-only edit also
  passed after direct human authorization, with local checks and independent review.
  Production behavior changes remain untested.
- **Codex ↔ Codex:** documented from the existing skill; not newly validated by
  the generalized experimental version.
- **Mixed Pi/Codex or other harnesses:** explicitly blocked before launch. A
  compatible return transport must be separately implemented and authorized.

The coordinator asks for Pi or Codex when the choice is not already explicit.
Harness and model are independent choices; the coordinator keeps its current
harness/model. A requested unsupported pairing is explained, never silently changed.

## Try explicitly, after agreeing on a task

For a Pi coordinator, both the skill and messaging extension must be loaded:

```sh
pi --skill /home/dev/factory/experiments/full-agents \
  -e /home/dev/factory/experiments/pi-agent-messaging/extension.mjs
```

This starts a new interactive conversation. To continue an existing one, agree
before stopping it and resume its exact session with the explicit extension/skill
arguments. Do not run a second writer against a live session file. Merely reading
the skill into a running Pi does not load the extension.

Invoke `/skill:full-agents` or explicitly ask the agent to read `SKILL.md`. For a
Codex coordinator, explicitly read this skill and its Codex adapter; do not install
or replace the existing skill as a side effect of trying the experiment.

See [the prototype plan](../../docs/pi-agents-prototype.md) for scope and evidence.
Keep both experiments in place during validation. Any future promotion to
`extensions/pi-agent-messaging/` and `skills/full-agents/` is a separate step;
update paths together rather than leaving live sessions with missing inputs.
