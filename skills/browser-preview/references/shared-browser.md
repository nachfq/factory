# Shared browser and GUI sessions

Use this mode when the user and agent need to inspect the same browser state,
including an installed extension, or interact with a desktop application.
An ordinary frontend usually only needs a web preview. Serving an extension's
HTML pages over HTTP does not reproduce its background worker or extension APIs.

## Reuse the session

First inspect the project's existing browser, display, profile and automation
connection. Connect the viewer to the display containing the browser the agent
controls. Keep its profile and open pages intact. A second browser with a fresh
profile does not share the original session.

If the project only has a headless browser, arrange a headed session using its
existing browser runner and test profile. Preserve any existing session before
replacing it. Keep profile data and runtime logs outside Git.

## Start the display only when needed

Reuse installed tools. On an Ubuntu agent environment, the optional desktop
components can be installed with:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  tigervnc-standalone-server tigervnc-common novnc websockify openbox xauth \
  x11-utils fonts-dejavu-core
```

Use the project's browser installation. These GUI components are project-level
dependencies, not a requirement for every agent or the base image.

The following is an example for an unused display and unused ports; adjust them
after checking the running processes and listeners. Run it as the project user.
Keep the resulting PIDs and logs so the session can be stopped independently.

```bash
runtime=$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/factory-shared-XXXXXX")
export DISPLAY=:77 XAUTHORITY="$runtime/Xauthority"
touch "$XAUTHORITY"
chmod 600 "$XAUTHORITY"
cookie=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
xauth -f "$XAUTHORITY" add "$DISPLAY" MIT-MAGIC-COOKIE-1 "$cookie"
unset cookie

Xtigervnc "$DISPLAY" -geometry 1600x1000 -depth 24 \
  -localhost yes -rfbport 5901 -SecurityTypes None -AlwaysShared \
  -auth "$XAUTHORITY" -nolisten tcp >"$runtime/vnc.log" 2>&1 &
vnc_pid=$!
if ! timeout 10s sh -c 'until xdpyinfo >/dev/null 2>&1; do sleep 0.1; done'; then
  cat "$runtime/vnc.log"
  kill "$vnc_pid"
  exit 1
fi
openbox >"$runtime/openbox.log" 2>&1 &
wm_pid=$!
websockify --web /usr/share/novnc 127.0.0.1:6080 127.0.0.1:5901 \
  >"$runtime/websockify.log" 2>&1 &
web_pid=$!
printf 'Runtime: %s\nVNC: %s\nWM: %s\nWeb: %s\n' \
  "$runtime" "$vnc_pid" "$wm_pid" "$web_pid"
```

Wait for the display to become ready before starting the project's headed browser
or GUI with the same `DISPLAY` and `XAUTHORITY`. Reuse its automation connection
(for example, browser DevTools) to observe the same browser the user sees.
Keep any automation listener on loopback too.

VNC authentication is omitted in this example because **both VNC and noVNC are
loopback-only and access uses the authenticated SSH preview tunnel**. Preserve
those bindings; an externally reachable desktop requires its own authentication
and is outside this recipe.

## Register and verify

Verify `vnc.html` and the WebSocket/RFB connection, then register the full viewer
URL using the existing preview command:

```bash
factory-preview 'http://localhost:6080/vnc.html?autoconnect=1&resize=remote&shared=1&quality=9&compression=2'
```

Deliver the registered link in the originating Herdr pane, following the main
skill's link and lifecycle rules. Check that the viewer and automation refer to
the same open page. Report a browser-access blocker instead of claiming a visual
verification from an HTTP 200 alone.

Shared mode allows both sides to control the same desktop. Coordinate input
during review, especially while the agent is running automation.

## Keep text sharp

- Prefer `resize=remote`: noVNC requests a framebuffer matching its viewport.
  TigerVNC normally accepts desktop resize requests. This changes the shared
  desktop dimensions, so keep one viewer responsible for resizing when several
  viewers are connected.
- Use `quality=9` for high JPEG quality. It improves encoded image quality but
  is not a lossless guarantee. `compression=2` is a CPU/bandwidth setting, not an
  image-quality control.
- A small fixed framebuffer enlarged with `resize=scale` can blur text. Compare
  `resize=off` at native size when diagnosing this. If remote resizing is not
  supported, choose a suitable fixed resolution before using scaling.
- Keep the local browser at 100% zoom while comparing. Check display pixel ratio
  on HiDPI screens; higher framebuffer resolution may help, but forcing every
  session to 4K increases rendering, memory and transport costs.

Quality changes normally need only a viewer reconnect with the new URL. Reuse the
running browser and VNC server. If visual inspection is unavailable, state which
protocol/settings checks passed and ask the user to judge the displayed result.

## Stop the owned session

Keep the session running while the user is reviewing it. When it is no longer
needed, remove its preview mapping and stop only the processes created for it,
using their recorded identities. Preserve the project's browser profile for a
later review when appropriate.

## Upstream references

- [noVNC URL options](https://github.com/novnc/noVNC/blob/master/docs/EMBEDDING.md)
- [noVNC resize and quality properties](https://github.com/novnc/noVNC/blob/master/docs/API.md)
- [TigerVNC display size and listener options](https://tigervnc.org/doc/Xvnc.html)
