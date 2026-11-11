#!/usr/bin/env python3
"""Install Factory's preview integration without changing Herdr configuration."""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/previews"
START = "<!-- factory:previews -->"
END = "<!-- /factory:previews -->"


def guidance_content(original, body):
    block = START + "\n" + body.strip() + "\n" + END
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise RuntimeError(
            "Malformed Factory preview guidance markers; original file preserved"
        )
    if START in original:
        first = original.index(START)
        last = original.index(END, first) + len(END)
        return original[:first] + block + original[last:]
    return (
        original
        + ("" if not original or original.endswith("\n") else "\n")
        + "\n"
        + block
        + "\n"
    )


def guidance_targets():
    codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    pi = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi/agent")
    for label, directory, names in [
        ("codex", codex, ["AGENTS.override.md", "AGENTS.md"]),
        (
            "pi",
            pi,
            ["AGENTS.override.md", "AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD"],
        ),
    ]:
        path = next(
            (
                directory / name
                for name in names
                if (directory / name).is_file()
                and (directory / name).read_text().strip()
            ),
            directory / "AGENTS.md",
        )
        yield label, path


def install():
    state = (
        Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        / "factory"
    )
    ledger = state / "previews-install.json"
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    links = {
        Path.home() / ".local/bin/factory-preview": PLUGIN / "preview.py",
        Path.home() / ".agents/skills/browser-preview": ROOT / "skills/browser-preview",
    }
    for target, source in links.items():
        if (
            os.path.lexists(target)
            and (not target.is_symlink() or target.resolve() != source.resolve())
            and (
                not target.is_symlink()
                or str(target.readlink()) != previous.get(str(target))
            )
        ):
            raise RuntimeError(f"Existing unrelated file: {target}")
    body = (ROOT / "config/agent-previews.md").read_text()
    guidance = []
    for label, path in guidance_targets():
        old = path.read_text() if path.exists() else ""
        guidance.append((label, path, old, guidance_content(old, body)))
    pin = json.loads((PLUGIN / "backend.json").read_text())
    if platform.system() != "Linux" or platform.machine() not in pin["platforms"]:
        raise RuntimeError("Previews currently support Linux x86_64 and aarch64")
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    destination = data / "factory/preview-backend" / pin["version"] / "forward"
    if not destination.exists():
        asset = pin["platforms"][platform.machine()]
        url = f"{pin['repository']}/releases/download/v{pin['version']}/herdr-forward_{pin['version']}_{asset['asset']}.tar.gz"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
            archive = Path(directory) / "backend.tar.gz"
            subprocess.run(
                ["curl", "-fsSL", "--retry", "3", url, "-o", str(archive)], check=True
            )
            if hashlib.sha256(archive.read_bytes()).hexdigest() != asset["sha256"]:
                raise RuntimeError("Preview backend checksum mismatch")
            with tarfile.open(archive, "r:gz") as bundle:
                member = next(
                    m for m in bundle if m.isfile() and Path(m.name).name == "forward"
                )
                with (
                    bundle.extractfile(member) as source,
                    (Path(directory) / "forward").open("wb") as target,
                ):
                    shutil.copyfileobj(source, target)
            staged = Path(directory) / "forward"
            staged.chmod(0o755)
            os.replace(staged, destination)
    for target, source in links.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if target.is_symlink():
            target.unlink()
        target.symlink_to(source, target_is_directory=source.is_dir())
    backup = state / "backups" / ("previews-" + str(time.time_ns()))
    for label, path, old, new in guidance:
        if old == new:
            continue
        if path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            saved = backup / (label + "-instructions.md")
            saved.write_text(old)
            saved.chmod(0o600)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)
    state.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({str(k): str(v) for k, v in links.items()}) + "\n")
    subprocess.run(["herdr", "plugin", "link", str(PLUGIN)], check=True)
    print("Installed Factory previews")


if __name__ == "__main__":
    install()
