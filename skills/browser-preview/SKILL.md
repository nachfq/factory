---
name: browser-preview
description: Deliver a ready browser preview when creating or changing a user-facing HTML artifact or frontend in a Factory environment. Use as part of delivery without waiting for the user to request a preview.
---

Give the user a working link they can Ctrl+click in this Herdr pane to open in
their laptop's browser. The preview stays in this container and travels over
the existing SSH connection.

Reuse the project's running development server when possible. Otherwise start
its normal dev command, bound to `127.0.0.1`, and keep it running in a dedicated
Herdr pane or a background process with a known PID and log. Keep the project's
existing port/config conventions when they work.

For a frontend with a backend, start or reuse both services and keep them running
for the preview. Prefer relative API URLs such as `/api/users`, using the project's
server-side development proxy to reach the backend inside the container. Configure
that proxy when needed: browser-side `localhost` refers to the user's laptop, and
the preview tunnel does not rewrite JavaScript URLs. Verify a representative API
request through the forwarded frontend URL and check the expected response; when
browser access is available, exercise the corresponding UI action too. A page
loading successfully alone does not verify its backend connection.

For a standalone HTML file, serve its containing directory with Python's HTTP
server so relative CSS, JavaScript and images remain available. For example:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory /absolute/artifact-directory
```

Choose another available remote port if needed. Verify the actual page responds,
then register its complete URL, including the HTML path, with:

```sh
factory-preview 'http://localhost:8000/report.html'
```

Successful output means the connected laptop has a ready tunnel. Include that
URL as a clickable link in the result, with the preview server still running.
Herdr's link handler resolves the correct container and any local-port conflict;
the displayed URL is contextual to this container's pane. Preserve this context
when passing a preview between agents in the same environment.

If registration fails, diagnose the server or client connection and report the
remaining failure accurately. A local file path or an unregistered container
localhost URL is not a working remote preview. When replacing an obsolete
preview, stop only the server you started and remove its mapping with
`factory-preview --stop URL`.
