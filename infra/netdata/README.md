# Optional Netdata on the Incus host

One host-level Netdata container monitors the server, Docker containers and
Incus instances through the host's process/cgroup views. It is independent of
the agent image and does not install anything inside project environments.

The official stable Docker image is pinned by digest. Its host PID/network
namespaces, read-only proc/sys mounts and extra capabilities allow host and
container collection. The Docker socket supplies container metadata. Host logs,
the Incus socket and the host root filesystem are not mounted.

## Start

Requires Docker Compose and the host's Tailscale connection. Copy this directory
to `~/services/netdata` on the server, then run there:

```bash
cp .env.example .env
# Set YOUR_TAILSCALE_IP in .env to this server's Tailscale IPv4.
docker compose config --quiet
docker compose up -d
```

The service binds only to the addresses in `NETDATA_LISTEN`. With no `.env`, it
defaults to loopback. On homelab it also binds the Tailscale IPv4; access is at
`http://TAILSCALE_IP:19999`. Docker's health check uses the loopback listener.
No router mapping, public DNS, Cloud enrollment or account login is needed.

This trial caps the service at 512 MiB RAM and half a CPU, collects every five
seconds, and disables ML/anomaly detection and alerts. One database tier has a
256 MiB retention target and a one-day time limit; the first limit reached
expires old samples. The size target is soft, and metadata/logs add overhead.
Configuration and metrics persist in Compose-managed volumes.

## Minimal resource view

Open `http://TAILSCALE_IP:19999/factory/index.html` for host CPU/RAM history and
disk usage, followed by the same metrics for each Factory Incus environment.
The 15-minute/1-hour/6-hour/24-hour selector queries Netdata's existing history.
Host CPU is a percentage of the whole machine; container CPU uses 100% per
core. RAM excludes swap, and host RAM usage excludes reclaimable cache/buffers.
The storage figures use GiB (1024³ bytes).

This is a small static page served by the existing Netdata web server, with no
frontend build, external assets, Cloud account or additional server. It refreshes
CPU/RAM every 15 seconds while visible; collection remains every five seconds.
Values above the charts use the latest raw samples, independently of the
selected history's averaging interval. Missing/stale data is marked explicitly.

### Storage sampling

The `dir` Incus pool does not expose per-instance disk usage in its state API.
Run the collector **on the host**, as a user in `incus-admin`, with Python 3 and
Incus installed:

```bash
cd ~/services/netdata
ionice -c 3 python3 collect-storage.py
```

It selects instances tagged `user.agent-env=true`, then sequentially executes
`nice -n 19 ionice -c 3 du -sx -B1 /` inside running instances. The guest needs
Python 3, coreutils and util-linux, already present in the agent image. No files
or software are installed in guests. This counts allocated blocks for their
root filesystem, including OS/tools/project files, and skips other filesystems.
Same-filesystem bind mounts can be counted. It is not full pool accounting:
images, snapshots and open-but-deleted files are not included, and shared/COW
blocks are not apportioned between instances.

Host totals/free space come from `statvfs('/')`, so the shared free space is
shown once. ext4's reserved space is displayed separately. For additional mounted
filesystems use e.g. `--host-path / --host-path /mnt/media` in the scheduled
command. Unmounted disks are not measured.

The collector has a nonblocking lock, a two-minute guest `du` timeout and a
140-second Incus command timeout. Stopped guests are never started. A failed
scan retains its timestamped last good value and marks the error; removed
environments disappear on the next successful host scan. JSON replacement is
atomic. Nice/ionice set best-effort priorities, not hard CPU/IO limits.

After the first successful run, schedule it every ten minutes. This preserves
existing crontab entries and replaces only this job's marked line:

```bash
{
  crontab -l 2>/dev/null | sed '/# factory-incus-storage$/d'
  printf '%s\n' '*/10 * * * * cd "$HOME/services/netdata" && /usr/bin/ionice -c 3 /usr/bin/python3 collect-storage.py > .collector-last-run.json 2>&1 # factory-incus-storage'
} | crontab -
```

The runtime snapshot `dashboard/incus-storage.json`, lock and last-run log are
ignored by Git. The page marks disk readings older than 18 minutes as stale.
The collector produces current disk readings; disk history is not ingested into
Netdata. CPU/RAM history comes from the existing Netdata database.

### Measure overhead

Every run prints its own benchmark to stdout, including each guest's wall time,
CPU seconds, peak RSS and physical filesystem reads/writes. The host's Python
process and Incus clients are measured separately. The reported RSS upper bound
adds their individual peaks plus the largest guest/du pair; this deliberately
overestimates simultaneous memory and is not an observed total peak. Incus daemon
overhead and unrelated workload are not attributed to this job.

Linux `ru_inblock * 512` counts physical reads, excluding cache hits. A warm-cache
run can therefore report zero disk reads while still traversing metadata. No
cache flush or IO stress is used. Measurements depend on file count, cache state
and concurrent work; larger/new environments can cost more.

Observed on 2026-11-09 with three running Ubuntu agent environments: 1.15–1.43 s
elapsed per complete scan. A warm run used 1.17 CPU-seconds including guest
supervisors and host clients: about 0.20% of one core averaged over ten minutes.
The largest individual process peaked near 28 MiB RSS; the conservative sum of
process peaks was about 65 MiB, transiently. The first scan read 3.35 MiB from
physical storage; repeated warm scans read zero. These are measurements of the
current working cache, not a cold-cache or large-project guarantee.

Validate the storage accounting/failure behavior and chart transformations:

```bash
python3 test-storage.py
node dashboard/test-metrics.js
```

## Inspect or remove

```bash
docker compose ps
docker stats --no-stream netdata
docker compose logs --tail 50
docker compose stop
docker compose start
```

`docker compose down` removes this service and keeps its data. To discard this
trial's stored configuration and history too, use `docker compose down --volumes`.
Other Docker services and Incus environments are unaffected by these commands.

If storage sampling was enabled, remove its cron job as well:

```bash
crontab -l | sed '/# factory-incus-storage$/d' | crontab -
```

## References

- [Official Docker installation](https://learn.netdata.cloud/docs/netdata-agent/installation/docker)
- [LXC/Incus collection](https://www.netdata.cloud/integrations/data-collection/containers-and-vms/lxc-containers/)
- [Database configuration](https://learn.netdata.cloud/docs/netdata-agent/configuration/database)
