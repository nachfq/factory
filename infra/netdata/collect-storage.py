#!/usr/bin/env python3
"""Snapshot allocated bytes for all Incus containers; no guest installation."""
import argparse
import fcntl
import json
import os
import re
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
        if instance["type"] != "container":
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


def statsd_payload(result):
    """Only publish new, successful samples; never freshen an old guest value."""
    lines = []
    for fs in result["filesystems"]:
        if fs["path"] == "/":
            for key in ("used", "available", "reserved"):
                gib = fs[key+"_bytes"] / 1024**3
                lines.append(f"factory.host.root.{key}:{gib:.9f}|g")
    for item in result["instances"]:
        if (item["status"] != "Running" or item.get("error")
                or "used_bytes" not in item
                or item.get("measured_at", 0) < result["updated_at"]):
            continue
        name = item["name"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ValueError("Unsafe instance name for StatsD")
        gib = item["used_bytes"] / 1024**3
        lines.append(f"factory.incus.{name}.used:{gib:.9f}|g|#units=GiB,family=incus_storage,name={name}")
    failures = sum(bool(item.get("error")) for item in result["instances"])
    lines.append(f"factory.collector.failures:{failures}|g|#units=instances,family=storage_collection,name=failed_scans")
    return ("\n".join(lines)+"\n").encode("ascii")


def publish_statsd(result):
    payload = statsd_payload(result)
    # Netdata can discard short TCP connections at EOF. StatsD's usual UDP
    # transport avoids that issue; each small datagram stays below the MTU.
    # Delivery is best-effort, with no application-level acknowledgement.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(2)
        connection.connect(("127.0.0.1", 8125))
        for line in payload.splitlines(keepends=True):
            if len(line) > 1200:
                raise ValueError("StatsD line exceeds datagram budget")
            connection.send(line)
    return len(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "dashboard" / "incus-storage.json")
    parser.add_argument("--host-path", action="append", default=None)
    parser.add_argument("--statsd", action="store_true", help="Publish fresh samples to local Netdata")
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
        if args.statsd:
            publish_start = time.monotonic()
            try:
                result["statsd_bytes_sent"] = publish_statsd(result)
            except (OSError, ValueError) as error:
                # Keep the local snapshot even if Netdata is restarting/down.
                result["statsd_error"] = str(error)
            result["benchmark"]["statsd_publish_ms"] = (time.monotonic()-publish_start)*1000
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
        if "statsd_error" in result:
            print("Netdata publishing failed: " + result["statsd_error"])
            raise SystemExit(1)


if __name__ == "__main__":
    main()
