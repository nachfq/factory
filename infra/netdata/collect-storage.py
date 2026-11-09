#!/usr/bin/env python3
"""Snapshot allocated bytes in running Factory instances; no guest installation."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import subprocess
import socket
import tempfile
import time


# Measure the actual guest process, not just the host's Incus client. Linux
# ru_inblock counts physical filesystem input in 512-byte blocks (cache excluded).
GUEST = r'''
import json, resource, subprocess, time
start = time.monotonic()
p = subprocess.run(["nice", "-n", "19", "ionice", "-c", "3", "du", "-sx", "-B1", "/"],
                   capture_output=True, text=True, timeout=120)
r = resource.getrusage(resource.RUSAGE_CHILDREN)
supervisor = resource.getrusage(resource.RUSAGE_SELF)
result = dict(wall_seconds=time.monotonic()-start,
              cpu_seconds=r.ru_utime+r.ru_stime+supervisor.ru_utime+supervisor.ru_stime,
              peak_rss_kib=r.ru_maxrss, supervisor_peak_rss_kib=supervisor.ru_maxrss,
              disk_read_bytes=r.ru_inblock*512, disk_write_bytes=r.ru_oublock*512)
if p.returncode:
    result["error"] = "du failed (filesystem may have changed); previous sample retained"
else:
    result["used_bytes"] = int(p.stdout.split()[0])
print(json.dumps(result))
'''


def collect_instance(name):
    p = subprocess.run(["incus", "exec", name, "--", "python3", "-c", GUEST],
                       capture_output=True, text=True, timeout=140)
    if p.returncode:
        raise RuntimeError("Incus measurement failed")
    return json.loads(p.stdout)


def snapshot(previous, host_paths, measure=collect_instance):
    instances = json.loads(subprocess.check_output(
        ["incus", "list", "--format", "json"], text=True, timeout=15))
    result = {"updated_at": time.time(), "interval_seconds": 600,
              "hostname": socket.gethostname(), "cpu_cores": os.cpu_count(),
              "filesystems": [], "instances": [], "benchmark": {}}
    for path in host_paths:
        s = os.statvfs(path)
        result["filesystems"].append({"path": path,
            "total_bytes": s.f_blocks*s.f_frsize,
            "used_bytes": (s.f_blocks-s.f_bfree)*s.f_frsize,
            "available_bytes": s.f_bavail*s.f_frsize,
            "reserved_bytes": (s.f_bfree-s.f_bavail)*s.f_frsize})
    old = {item["name"]: item for item in previous.get("instances", [])}
    measurements = []
    for instance in instances:
        if instance.get("config", {}).get("user.agent-env") != "true":
            continue
        name = instance["name"]
        item = {"name": name, "status": instance["status"]}
        config = instance.get("expanded_config", instance.get("config", {}))
        item["cpu_limit"] = config.get("limits.cpu")
        item["memory_limit"] = config.get("limits.memory")
        # Keep a timestamped last good value for stopped/failed environments.
        for key in ("used_bytes", "measured_at"):
            if key in old.get(name, {}):
                item[key] = old[name][key]
        if instance["status"] == "Running":
            try:
                sample = measure(name)
                measurements.append({"name": name, **sample})
                if "error" in sample:
                    item["error"] = sample["error"]
                else:
                    item.update(used_bytes=sample["used_bytes"], measured_at=time.time())
            except (subprocess.SubprocessError, RuntimeError, ValueError, KeyError):
                item["error"] = "Measurement unavailable; previous sample retained"
        result["instances"].append(item)
    result["benchmark"]["instances"] = measurements
    result["benchmark"]["guest_cpu_seconds"] = sum(x["cpu_seconds"] for x in measurements)
    result["benchmark"]["guest_disk_read_bytes"] = sum(x["disk_read_bytes"] for x in measurements)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "dashboard" / "incus-storage.json")
    parser.add_argument("--host-path", action="append", default=None)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # One job at a time; no backlog when an earlier scan takes longer.
    with (args.output.parent.parent / ".collector.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        os.nice(19)
        start = time.monotonic()
        try:
            previous = json.loads(args.output.read_text())
        except (FileNotFoundError, ValueError):
            previous = {}
        result = snapshot(previous, args.host_path or ["/"])
        own = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        result["benchmark"].update(wall_seconds=time.monotonic()-start,
            host_cpu_seconds=own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime,
            host_peak_rss_kib=max(own.ru_maxrss, children.ru_maxrss))
        result["benchmark"]["rss_upper_bound_kib"] = own.ru_maxrss+children.ru_maxrss+max(
            (x["peak_rss_kib"]+x["supervisor_peak_rss_kib"]
             for x in result["benchmark"]["instances"]), default=0)
        # Readers see the complete previous or new sample, never half-written JSON.
        with tempfile.NamedTemporaryFile("w", dir=args.output.parent, delete=False) as f:
            json.dump(result, f, separators=(",", ":"))
            temporary = f.name
        os.chmod(temporary, 0o644)
        os.replace(temporary, args.output)
        print(json.dumps(result["benchmark"], indent=2))


if __name__ == "__main__":
    main()
