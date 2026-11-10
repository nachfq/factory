#!/usr/bin/env python3
"""Project environment client for a local or SSH-connected Incus host."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time


HOME = Path.home()
HOST = os.environ.get("AGENT_ENV_HOST", "nacho@homelab")
IMAGE = os.environ.get("AGENT_ENV_IMAGE", "agent-base")
SSH_DIR = HOME / ".ssh"
SSH_CONFIG = SSH_DIR / "agent-env.conf"
KNOWN_HOSTS = SSH_DIR / "agent-env_known_hosts"
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "agent-env"
KEY_NAME = "agent-env_ed25519" if HOST == "local" else "id_ed25519"


def run(args, *, text=None, capture=True):
    result = subprocess.run(args, input=text if text is not None else "", text=True, capture_output=capture)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f"Command failed: {args[0]}").strip())
    return result.stdout.strip() if capture else ""


def host(*args, text=None):
    if HOST == "local":
        return run(list(args), text=text)
    return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST,
                shlex.join(list(args))], text=text)


def incus(*args, text=None):
    return host("incus", *args, text=text)


def instance_name(name):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", name):
        raise RuntimeError("Use a short name with lowercase letters, numbers and hyphens.")
    return "dev-" + name


def instances():
    return json.loads(incus("list", "--format", "json"))


def managed(name):
    instance = instance_name(name)
    matches = [item for item in instances() if item["name"] == instance]
    if not matches or matches[0].get("config", {}).get("user.agent-env") != "true":
        raise RuntimeError(f"{instance} is not an environment managed by this command.")
    return matches[0]


def ip_address(item):
    network = (item.get("state") or {}).get("network") or {}
    for address in network.get("eth0", {}).get("addresses", []):
        if address["family"] == "inet" and address.get("scope") == "global":
            return address["address"]
    return None


def wait_for_ip(name):
    for _ in range(40):
        address = ip_address(managed(name))
        if address:
            return address
        time.sleep(0.5)
    raise RuntimeError("The environment has no IPv4 address yet. Retry open in a moment.")


def write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o600)


def public_key():
    key = SSH_DIR / KEY_NAME
    public = key.with_suffix(".pub")
    if HOST == "local" and not key.exists() and not public.exists():
        SSH_DIR.mkdir(mode=0o700, exist_ok=True)
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key),
             "-C", "agent-env Incus host"])
    if not public.is_file():
        raise RuntimeError(f"Missing client public key: {public}")
    return public


def authorize_local_access(instance):
    # Add this client's public key without replacing laptop or other client keys.
    incus("exec", instance, "--", "sh", "-ec",
          'key=$(cat); test -n "$key"; '
          'install -d -m 700 -o dev -g dev /home/dev/.ssh; '
          'touch /home/dev/.ssh/authorized_keys; '
          'grep -qxF -- "$key" /home/dev/.ssh/authorized_keys || '
          'printf "\\n%s\\n" "$key" >> /home/dev/.ssh/authorized_keys; '
          'chown dev:dev /home/dev/.ssh/authorized_keys; '
          'chmod 600 /home/dev/.ssh/authorized_keys', text=public_key().read_text())


def save_connection(name, address, public_host_key):
    SSH_DIR.mkdir(mode=0o700, exist_ok=True)
    config = SSH_DIR / "config"
    include = "Include ~/.ssh/agent-env.conf"
    original = config.read_text() if config.exists() else ""
    if include not in original.splitlines():
        if config.exists():
            STATE.mkdir(parents=True, exist_ok=True)
            shutil.copy2(config, STATE / f"ssh-config-{time.time_ns()}.backup")
        write_private(config, include + "\n\n" + original)
    target = "agent-" + name
    state_file = STATE / f"{name}.json"
    previous = json.loads(state_file.read_text()) if state_file.exists() else {}
    state = {**previous, "target": target, "ip": address, "host_key": public_host_key,
             "host": HOST, "identity_file": "~/.ssh/" + KEY_NAME,
             "label": "homelab / " + name}
    STATE.mkdir(parents=True, exist_ok=True)
    write_private(STATE / f"{name}.json", json.dumps(state, indent=2) + "\n")
    rebuild_connections()
    return state


def rebuild_connections():
    blocks, keys = [], []
    for file in sorted(STATE.glob("*.json")):
        state = json.loads(file.read_text())
        alias = "agent-env-" + file.stem
        proxy = f'    ProxyJump {state["host"]}\n' if state["host"] != "local" else ""
        blocks.append(f'Host {state["target"]}\n'
                      f'    HostName {state["ip"]}\n'
                      '    User dev\n'
                      + proxy +
                      f'    IdentityFile {state.get("identity_file", "~/.ssh/id_ed25519")}\n'
                      '    IdentitiesOnly yes\n'
                      f'    HostKeyAlias {alias}\n'
                      '    UserKnownHostsFile ~/.ssh/agent-env_known_hosts\n'
                      '    StrictHostKeyChecking yes\n')
        keys.append(alias + " " + state["host_key"])
    write_private(SSH_CONFIG, "\n".join(blocks))
    write_private(KNOWN_HOSTS, "\n".join(keys) + "\n")


def herdr(*args, machine=None):
    prefix = ["herdr"] + (["--machine", machine] if machine else [])
    output = run(prefix + list(args))
    return json.loads(output) if output else None


def ensure_server(target):
    status = run(["ssh", "-o", "BatchMode=yes", target, "/home/dev/.local/bin/herdr status server"])
    if "status: running" in status:
        return False
    command = ('nohup /home/dev/.local/bin/herdr server '
               '>/home/dev/.config/herdr/server-start.log 2>&1 </dev/null &')
    run(["ssh", "-o", "BatchMode=yes", target, shlex.join(["sh", "-c", command])])
    for _ in range(30):
        status = run(["ssh", "-o", "BatchMode=yes", target, "/home/dev/.local/bin/herdr status server"])
        if "status: running" in status:
            return True
        time.sleep(0.2)
    raise RuntimeError("Herdr did not start. Inspect ~/.config/herdr/server-start.log in the environment.")


def start_project_panes(state, machine):
    left, right = state["left_pane"], state["right_pane"]
    available = []
    for pane in (left, right):
        info = herdr("pane", "process-info", "--pane", pane, machine=machine)["result"]["process_info"]
        processes = info.get("foreground_processes", [])
        if processes and all(p["name"] in ("bash", "zsh", "fish") for p in processes):
            available.append(pane)
    if right in available:
        herdr("pane", "run", right, "nvim .", machine=machine)
    if left not in available:
        return
    authed = subprocess.run(["ssh", "-o", "BatchMode=yes", state["target"],
                             "/home/dev/.local/bin/codex login status"],
                            capture_output=True).returncode == 0
    if authed:
        herdr("agent", "start", "main", "--kind", "codex", "--pane", left,
              "--timeout", "20000", "--", "--yolo", machine=machine)
    else:
        message = ("Entorno listo. Logins propios de este entorno:\n"
                   "  gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key\n"
                   "  gh auth setup-git --hostname github.com\n"
                   "  codex login --device-auth\n"
                   "Despues ejecuta: codex\n")
        herdr("pane", "run", left, "printf %s " + shlex.quote(message), machine=machine)


def connect(name):
    item = managed(name)
    instance = item["name"]
    if item["status"] != "Running":
        incus("start", instance)
    address = wait_for_ip(name)
    if HOST == "local":
        authorize_local_access(instance)
    # The host key is obtained through the trusted host + Incus channel.
    host_key = incus("exec", instance, "--", "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
    state = save_connection(name, address, host_key)
    profiles = json.loads(run(["herdr", "machine", "list", "--json"]))
    matching = [p for p in profiles if p["target"] == state["target"] and p["label"] == state["label"]]
    revived = False
    if matching:
        revived = ensure_server(state["target"])
    else:
        run(["herdr", "machine", "add", state["target"], "--label", state["label"]])
        profiles = json.loads(run(["herdr", "machine", "list", "--json"]))
        matching = [p for p in profiles if p["target"] == state["target"] and p["label"] == state["label"]]
    if len(matching) != 1:
        raise RuntimeError("More than one Herdr connection matches this environment; remove its duplicate profile.")
    machine = matching[0]["id"]
    cwd = item["config"]["user.agent-env.cwd"]
    workspaces = herdr("workspace", "list", machine=machine)["result"]["workspaces"]
    if not any(w.get("label") == name for w in workspaces):
        result = herdr("workspace", "create", "--label", name, "--cwd", cwd,
                       "--no-focus", machine=machine)["result"]
        left = result["root_pane"]["pane_id"]
        right = herdr("pane", "split", left, "--direction", "right", "--cwd", cwd,
                      "--no-focus", machine=machine)["result"]["pane"]["pane_id"]
        state.update(left_pane=left, right_pane=right)
        write_private(STATE / f"{name}.json", json.dumps(state, indent=2) + "\n")
        start_project_panes(state, machine)
        if len(workspaces) == 1 and workspaces[0].get("label") == "~" and workspaces[0].get("pane_count") == 1:
            # This empty home workspace was created by our initial server setup.
            herdr("workspace", "close", workspaces[0]["workspace_id"], machine=machine)
    elif revived and state.get("left_pane") and state.get("right_pane"):
        start_project_panes(state, machine)
    print(f'Available in Herdr: {state["label"]} → {name}')
    print(f'SSH: ssh {state["target"]}   Project: {cwd}')


def create(name, repo):
    instance = instance_name(name)
    version = json.loads(incus("query", "/1.0"))["environment"]["server_version"]
    numbers = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not numbers or tuple(map(int, numbers.groups())) < (6, 0, 1):
        raise RuntimeError("Incus 6.0.1 or newer is required: 6.0.0 skips dev folders when unpacking images.")
    if any(item["name"] == instance for item in instances()):
        raise RuntimeError(f"{instance} already exists. Use open {name}.")
    key = public_key()
    if repo and not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", repo):
        raise RuntimeError("Use a GitHub HTTPS repository URL without credentials.")
    cwd = "/home/dev/" + name
    incus("launch", IMAGE, instance, "-p", "agent-pilot", "-c", "user.agent-env=true",
          "-c", "user.agent-env.name=" + name, "-c", "user.agent-env.cwd=" + cwd)
    print(f"Created {instance}. Preparing SSH...")
    # Wait for systemd's control socket before provisioning. First boot can also
    # exhaust SSH's restart limit while the image still has no host keys.
    # Stop both SSH units to avoid racing their automatic retries.
    incus("exec", instance, "--", "sh", "-ec",
          'attempt=0; until systemctl show-environment >/dev/null 2>&1; do '
          'attempt=$((attempt + 1)); '
          '[ "$attempt" -lt 60 ] || { echo "systemd is not ready" >&2; exit 1; }; '
          'sleep 0.5; done; '
          'systemctl stop ssh.socket ssh.service; '
          'ssh-keygen -A; install -d -m 700 -o dev -g dev /home/dev/.ssh; '
          'cat > /home/dev/.ssh/authorized_keys; '
          'chown dev:dev /home/dev/.ssh/authorized_keys; '
          'chmod 600 /home/dev/.ssh/authorized_keys; '
          'systemctl reset-failed ssh.service ssh.socket; '
          'systemctl start ssh.service; '
          'systemctl is-active --quiet ssh.service', text=key.read_text())
    # The first published base used a detached build revision. Restore the local
    # main branch without fetching or changing the image's versioned contents.
    incus("exec", instance, "--", "runuser", "-u", "dev", "--",
          "git", "-C", "/home/dev/dotfiles", "switch", "main")
    for key in ("user.name", "user.email"):
        value = subprocess.run(["git", "config", "--global", "--get", key],
                               capture_output=True, text=True)
        if value.returncode == 0 and value.stdout.strip():
            incus("exec", instance, "--", "runuser", "-u", "dev", "--",
                  "git", "config", "--global", key, value.stdout.strip())
    address = wait_for_ip(name)
    if repo:
        try:
            incus("exec", instance, "--", "runuser", "-u", "dev", "--", "env", "GIT_TERMINAL_PROMPT=0",
                  "git", "clone", repo, cwd)
        except RuntimeError as error:
            print(f"Clone needs attention after login: {error}", file=sys.stderr)
            incus("exec", instance, "--", "install", "-d", "-o", "dev", "-g", "dev", cwd)
    else:
        incus("exec", instance, "--", "install", "-d", "-o", "dev", "-g", "dev", cwd)
    # Apply the laptop's versioned defaults even when the cached image is older.
    incus("exec", instance, "--", "runuser", "-u", "dev", "--", "python3", "-",
          text=Path(__file__).resolve().with_name("configure-codex.py").read_text())
    incus("config", "device", "override", instance, "eth0", "ipv4.address=" + address)
    connect(name)


def remove(name):
    item = managed(name)
    state_file = STATE / f"{name}.json"
    if state_file.exists():
        state = json.loads(state_file.read_text())
        profiles = json.loads(run(["herdr", "machine", "list", "--json"]))
        for profile in profiles:
            if profile["target"] == state["target"] and profile["label"] == state["label"]:
                run(["herdr", "machine", "remove", profile["id"]])
    incus("delete", item["name"], "--force")
    state_file.unlink(missing_ok=True)
    rebuild_connections()
    print(f'Deleted {item["name"]}, its filesystem and local connection entries.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="Create from agent-base and add to Herdr")
    new.add_argument("name")
    new.add_argument("repo", nargs="?")
    opening = commands.add_parser("open", help="Start if stopped and make available in Herdr")
    opening.add_argument("name")
    listing = commands.add_parser("list", help="List environments managed by this command")
    listing.add_argument("--names", action="store_true", help="Print only environment names")
    deletion = commands.add_parser("remove", help="Permanently delete an environment and its files")
    deletion.add_argument("name")
    args = parser.parse_args()
    if args.command != "list" and os.environ.get("HERDR_ENV") != "1":
        raise RuntimeError("Run this command inside Herdr on this client.")
    if args.command == "new":
        create(args.name, args.repo)
    elif args.command == "open":
        connect(args.name)
    elif args.command == "remove":
        remove(args.name)
    else:
        if not args.names:
            print(f'{"NAME":<24} {"STATUS":<12} IP')
        for item in instances():
            if item.get("config", {}).get("user.agent-env") == "true":
                name = item["config"]["user.agent-env.name"]
                if args.names:
                    print(name)
                else:
                    print(f'{name:<24} {item["status"]:<12} {ip_address(item) or "-"}')


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
