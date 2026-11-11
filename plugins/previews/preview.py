#!/usr/bin/env python3
"""Register a ready container URL, or open it through the local Herdr client."""

import argparse
import fcntl
import json
import os
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
PLUGIN = "factory.previews"


def backend_binary():
    version = json.loads((ROOT / "backend.json").read_text())["version"]
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    binary = data / "factory/preview-backend" / version / "forward"
    if not binary.is_file():
        raise RuntimeError("Run Factory setup-agent.sh install-previews first")
    return binary


def state_dir():
    return Path(
        os.environ.get("HERDR_PLUGIN_STATE_DIR")
        or Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        / "herdr/plugins"
        / PLUGIN
    )


def backend_environment():
    return os.environ | {
        "HERDR_PLUGIN_ROOT": str(ROOT),
        "HERDR_PLUGIN_STATE_DIR": str(state_dir()),
    }


def run(argv, **kwargs):
    result = subprocess.run(
        list(map(str, argv)),
        check=False,
        capture_output=True,
        text=True,
        timeout=25,
        **kwargs,
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "Preview command failed"
        )
    return result.stdout.strip()


def backend(*args):
    return run([backend_binary(), *args], env=backend_environment())


def herdr(*args):
    data = json.loads(run([os.environ.get("HERDR_BIN_PATH") or "herdr", *args]))
    return data.get("result", data) if isinstance(data, dict) else data


def validate_url(url):
    if not isinstance(url, str) or any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("Preview URL contains invalid characters")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("localhost", "127.0.0.1")
        or parsed.username
        or parsed.password
        or not parsed.port
        or not 1024 <= parsed.port <= 65535
    ):
        raise ValueError(
            "Preview URL must use http(s), loopback and a port between 1024 and 65535"
        )
    return parsed


def register(url):
    parsed = validate_url(url)
    # The agent publishes only a URL whose remote server already responds.
    with urlopen(url, timeout=5) as response:
        if response.status >= 400:
            raise RuntimeError("Preview server did not return a successful response")
    sessions = json.loads(backend("bridge", "status", "--json")).get("sessions", [])
    if not sessions:
        raise RuntimeError(
            "No preview client connected. Reopen this environment from the laptop with agent-env open."
        )
    records = json.loads(backend("list", "--json"))["forwards"]
    existing = next(
        (
            r
            for r in records
            if r.get("mode") == "client" and r.get("remote_port") == parsed.port
        ),
        None,
    )
    if existing and existing.get("status") == "up":
        return url
    candidates = [parsed.port] + [53000 + secrets.randbelow(11000) for _ in range(4)]
    if existing:
        backend("remove", existing["id"])
    for local in candidates:
        if any(r["local_port"] == local for r in records):
            continue
        identifier = backend("add", f"{local}:{parsed.port}", "--client").splitlines()[
            -1
        ]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rows = json.loads(backend("list", "--json"))["forwards"]
            record = next((r for r in rows if r["id"] == identifier), None)
            if record and record.get("status") == "up":
                return url
            if record and record.get("status") == "down":
                break
            time.sleep(0.25)
        backend("remove", identifier)
    raise RuntimeError("Could not allocate a preview port on the connected client")


def update_activation(machine, record):
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "activated-machines.json"
    with (directory / ".activation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        doc = (
            json.loads(path.read_text())
            if path.exists()
            else {"version": 1, "active": None, "machines": {}}
        )
        if record is None:
            doc["machines"].pop(machine, None)
        else:
            doc["machines"][machine] = record
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as stream:
            json.dump(doc, stream)
            temporary = stream.name
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)


def attach(machine):
    profiles = herdr("machine", "list", "--json")
    profile = next((p for p in profiles if p["id"] == machine and p["enabled"]), None)
    if not profile:
        raise RuntimeError("Preview machine is not an enabled Herdr connection")
    plugins = herdr("--machine", machine, "plugin", "list", "--json")["plugins"]
    plugin = next(
        (p for p in plugins if p["plugin_id"] == PLUGIN and p["enabled"]), None
    )
    if not plugin:
        raise RuntimeError("This environment needs Factory install-previews")
    root = plugin["plugin_root"]
    command = shlex.join(["python3", root + "/preview.py", "--location"])
    location = json.loads(
        run(["ssh", "-o", "BatchMode=yes", profile["target"], command])
    )
    update_activation(
        machine,
        {
            "label": profile["label"],
            "ssh_target": profile["target"],
            "server_root": location["root"],
            "state_dir": location["state"],
            "local": False,
            "activated_unix": int(time.time()),
        },
    )
    backend("bridge", "up", machine)


def restore():
    # A startup hook only restores previously selected connections, then exits.
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return
    path = state_dir() / "activated-machines.json"
    if not path.exists():
        return
    enabled = {p["id"] for p in herdr("machine", "list", "--json") if p["enabled"]}
    for machine in json.loads(path.read_text())["machines"]:
        if machine in enabled:
            backend("bridge", "up", machine)
        else:
            backend("bridge", "down", machine)
            update_activation(machine, None)


def stop(url):
    port = validate_url(url).port
    records = json.loads(backend("list", "--json"))["forwards"]
    for record in records:
        if record.get("mode") == "client" and record.get("remote_port") == port:
            backend("remove", record["id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--handle-link", action="store_true")
    parser.add_argument("--attach", metavar="MACHINE")
    parser.add_argument("--detach", metavar="MACHINE")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--location", action="store_true")
    parser.add_argument("--stop", metavar="URL")
    args = parser.parse_args()
    if args.location:
        print(json.dumps({"root": str(ROOT), "state": str(state_dir())}))
    elif args.attach:
        attach(args.attach)
    elif args.detach:
        backend("bridge", "down", args.detach)
        update_activation(args.detach, None)
    elif args.restore:
        restore()
    elif args.stop:
        stop(args.stop)
    elif args.handle_link:
        url = os.environ.get("HERDR_PLUGIN_CLICKED_URL") or json.loads(
            os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}")
        ).get("clicked_url")
        validate_url(url)
        backend("open-url", url)
    elif args.url:
        directory = state_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Several agents can deliver previews concurrently in the same container.
        with (directory / ".register.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            print(register(args.url))
    else:
        parser.error("Pass the running preview URL")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
