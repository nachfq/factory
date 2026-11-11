# Browser previews

Agents deliver a running HTML/frontend preview as a URL in their Herdr pane.
Ctrl+click opens it in the laptop's normal browser through SSH. The dev server
and project files remain inside the container. The integration supports the
saved SSH machines created by `agent-env`, including their jump hosts and keys.

## Install

As the regular user on the laptop:

```bash
./setup-agent.sh install-previews
agent-env open NAME
```

The base-image recipe includes the same installation for container users.
Existing environments can install it from an updated Factory checkout with
`./setup-agent.sh install-previews`. Preserve unrelated checkout changes when
updating. The command downloads a checksum-pinned transport, links the small
`factory.previews` Herdr plugin and `factory-preview`, and installs the
`browser-preview` skill. It does not edit Herdr's config, keys or tab bar.

`config/agent-previews.md` is inserted as a managed block into each harness's
active global instructions, honoring `CODEX_HOME` and `PI_CODING_AGENT_DIR`.
Other instructions are preserved and backed up privately under Factory's state
directory before a change. Codex loads the pointer in new sessions; Pi also
reloads resources/instructions with `/reload`.

## Delivery and links

The shared skill makes preview delivery part of creating a user-facing HTML
artifact or frontend. The agent starts or reuses an appropriate development
server, verifies its page, and calls `factory-preview URL`. A successful call
means the laptop has acknowledged a ready mapping. It then gives that URL to
the user. A disconnected client or failed server is reported as a failure,
rather than a ready preview.

The visible loopback URL belongs to the originating container. Open it with
Ctrl+click **in that container's Herdr pane**: the handler resolves its mapping
and opens the actual laptop URL. If two projects use the same remote port, the
second can receive a different laptop port automatically. Paths, queries and
fragments are preserved. Copying a contextual URL directly into a browser skips
the handler and may reach another project's port.

SSH forwards TCP, so relative assets and WebSockets work without an HTTP proxy
or subpath rewrite. Development servers that hard-code an external origin may
still need their usual project configuration. The laptop browser runs the page's
JavaScript as normal. The current client flow targets a graphical Linux laptop;
`agent-env`'s headless local-host mode does not start a browser transport.

Keep a preview's server running while the user reviews it. The agent can stop
its own obsolete server and remove that mapping with `factory-preview --stop URL`.
`agent-env remove` tears down that client's preview connection before deleting
the container. No preview port is bound to the LAN or published to the internet.

## Transport and lifecycle

The SSH transport is the unmodified MIT-licensed
[herdr-forward](https://github.com/zzjcool/herdr-forward) v0.4.0 binary. Its
release archive SHA-256 values and source are pinned in
`plugins/previews/backend.json`; the installer verifies the archive before
extracting its executable. Factory supplies its own minimal manifest and
adapter instead of upstream's automatic keybinding/tab-bar installers.

The binary is cached under `~/.local/share/factory/preview-backend/VERSION/`.
Runtime mappings and client connections are private, per-user Herdr plugin state.
`agent-env open/new` derives the selected target from Herdr's saved profile and
starts one SSH transport for it. The plugin's one-shot startup hook restores
previously selected, still-enabled connections after a Herdr server restart.
The transport reconnects after an SSH interruption and exits when its owning
Herdr server stops. There is no port-scanning process inside the container.

Factory serializes preview registration in each container. A busy laptop port
causes a bounded retry with a different port; the helper waits for the client
acknowledgement before reporting success. SSH and backend records handle their
own connection locks; Factory's activation ledger is written atomically.

## Validation

Unit tests cover URL boundaries, missing clients and preservation/idempotency
of global instructions. The live check used two disposable Incus environments
serving the same remote port, verified the correct HTML and relative CSS through
both mappings, and exercised a real Vite dev server plus its HMR WebSocket over
the remapped port. Browser dispatch was captured with a test opener without
changing the desktop's default browser.
Concurrent registrations, reconnecting an existing mapping and removing it were
also checked against the disposable environments.
