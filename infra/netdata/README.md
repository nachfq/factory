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

## Simple resource dashboard

Open `http://TAILSCALE_IP:19999/factory/index.html` for the compact everyday view:
one server row, then its Factory containers ordered by occupied disk space.
CPU and RAM show the last hour with the current value above each graph; disk
is numeric only. The host also shows available disk space. There are no menus
or time-range controls. Hover a graph, or focus it and use the arrow keys, for
an individual timestamp/value. The UI is in English and uses Catppuccin Mocha,
with a local SVG favicon. Labels are kept to metrics, capacity and freshness.

CPU percentages use the **whole host** as denominator for both host and guest
rows: the container's cgroup percentage is divided by the host's core count.
This differs from native Netdata's 100%-per-core container CPU convention.
Every row shares the same zero-based CPU and RAM graph scales, so a small
container isn't visually magnified relative to the host or another container.
Host RAM is estimated used memory, **MemTotal minus MemAvailable**, with the
current available memory shown below it. Historical used values subtract each
available-memory sample from the current host total (appropriate for this host's
fixed physical memory). Missing available-memory samples remain missing, with no
fallback to the previous incompatible "used" definition.

Container RAM is cgroup memory usage minus **inactive file cache and reclaimable
kernel slab**, excluding swap. This removes filesystem metadata cache that can
otherwise look like application RAM after builds or repository scans. It remains
an estimate: active file cache can still be included, and it is not directly
additive with the host estimate. Each container shows its configured
Incus memory limit below the current value, e.g. `1.7 GiB` / `of 2 GiB`. Limits
come from the same ten-minute instance snapshot; percentage limits are identified
as a share of host memory and absent limits are explicit. Storage uses GiB.

The view refreshes every 15 seconds while visible. The instance list and disk
measurements update on the collector's ten-minute cadence, so additions/removals
appear automatically after its next successful scan. Missing/stale readings
remain visibly unavailable; stopped containers can retain dimmed recent history
and their timestamped last known disk measurement. No import or layout editing
is needed when environments change.

The HTML/CSS/JS are served by the existing Netdata web server. No framework,
external assets, separate service or agent image change is required. Historical data
comes from Netdata and current disk/list data from the atomic JSON snapshot.

### Container RAM collection

`factory-memory.plugin` is a small Python collector supervised by Netdata itself.
Every ten seconds it reads `memory.current`, `inactive_file` and
`slab_reclaimable` from the host's top-level Incus payload cgroups. It uses the
existing read-only `/host/sys` mount and the Factory instance snapshot to select
guests. It does not run Incus commands, launch guest processes or change cgroup
limits. Python 3 is already present in the pinned Netdata image.

The plugin is mounted read-only into Netdata's `plugins.d` directory and enabled
by `netdata.conf`. Its `factory_memory.INSTANCE` charts store corrected MiB in
Netdata's existing database, under context `factory.container_memory`. The custom
dashboard uses these charts directly. History begins when this collector is
enabled; it never mixes older working-set values into the new series. Missing or
inconsistent counters produce missing data rather than fabricated zeroes. Stopped
and deleted guests stop publishing; the instance list still updates on its usual
ten-minute snapshot cadence. Host RAM and CPU collection are unchanged.

Measure the collector's incremental read/parse cost without publishing anything:

```bash
docker exec -u netdata netdata /usr/libexec/netdata/plugins.d/factory-memory.plugin 10 --benchmark 1000
```

On homelab with four running containers, 1,000 passes measured **0.67 ms CPU per
pass**, equivalent to **0.0067% of one CPU** at the ten-second interval. Peak
Python RSS was **12.5 MiB**; physical reads totalled **252 KiB** across the full
benchmark. This measures the reader, excluding Netdata's own chart/database work.
The benchmark also reports wall time, errors and the number of measured guests.

### Short private URL

With MagicDNS enabled, Tailscale Serve can expose the dashboard as
`http://HOSTNAME/factory/` without a port, leaving the root for other services.
On the server, first inspect
`tailscale serve status` and check that port 80 is not already assigned. Run as
the configured Tailscale operator (or with sudo):

```bash
tailscale serve --bg --http=80 --set-path=/factory http://127.0.0.1:19999/factory/
tailscale serve --bg --http=80 --set-path=/factory/api http://127.0.0.1:19999/api/
tailscale serve status
```

The `/factory` route serves the dashboard and its relative assets/snapshot;
`/factory/api` forwards its data queries. The HTML base path keeps assets working
with or without a trailing slash. The frontend discovers the scoped API once,
falling back to native Netdata's `/api` when used on its original port. No global
root or `/api` route is assigned. Both backend target paths are intentional.
Serve runs inside the existing Tailscale daemon and `--bg`
persists the configuration. Access remains within the tailnet, using its existing
access policy; Funnel/public sharing is not enabled. This HTTP URL travels over
Tailscale's encrypted network. The original `:19999/factory/` URL still works.

To remove only this dashboard shortcut, preserving other services on port 80:

```bash
tailscale serve --http=80 --set-path=/factory/api off
tailscale serve --http=80 --set-path=/factory off
```

## Optional native Netdata resource view

Disk samples are published by the same host collector to Netdata's built-in
StatsD listener, bound only to `127.0.0.1:8125/UDP`. No additional service or
container agent is needed. Standard CPU/RAM charts retain their existing
definitions; the corrected RAM series is available as `factory.container_memory`.

Open the main Netdata page, then the **Metrics**/node charts and **StatsD**:

- `host_storage`: root filesystem used, available and reserved space in one
  stacked GiB chart, context `statsd_factory.host_disk_space`.
- `incus_storage`: one GiB gauge per running Factory instance, with its name as
  the dimension. Contexts are `statsd_factory.incus.INSTANCE.used_gauge`.
- `storage_collection`: count of failed guest scans, expected to be zero.

The standard CPU/RAM contexts are `system.cpu`, `system.ram`, `cgroup.cpu` and
`cgroup.mem_usage`. Container CPU uses 100% per core; host CPU uses 100% for the
whole machine. For RAM choose `used` on the host and `ram` in containers to
exclude reclaimable host cache and guest swap respectively.

For a compact layout, create **Dashboards → + → Resources**, add those host
contexts and the desired container contexts, then **Save**. On shared cgroup
charts select only the `dev-*` instances (exclude Docker and `lxc.monitor.*`)
and group by instance when comparing environments. A newly created environment
gets its own disk chart in StatsD after the next scan; a layout selecting
individual contexts needs that new chart added. The native dashboard layout is
configured through the browser, separately from the server's collector config.

To create the complete layout as an importable file instead of adding cards
manually, run this on any machine that can reach the private Netdata address:

```bash
python3 make-dashboard.py --url http://TAILSCALE_IP:19999 --output ~/Downloads/Recursos.json
```

In the dashboard editor, use the **up-arrow/import** button beside its name,
select `Recursos.json`, then **Save**. The file contains three host charts and
one CPU/RAM/disk row per current Factory instance. Regenerate and reimport it
after adding/removing environments. Each row uses three four-track cards in
Netdata's twelve-track grid, fitting the available width. Import replaces the
current layout; export it first if you want to keep manual changes. Generated
files include instance names and should stay outside the public checkout
(`Recursos.json` is ignored).
The original exported dashboard remains untouched.

`native-card-template.json` preserves the standard chart attributes exported by
the bundled Netdata UI 7.136.1. The generator uses that native import format,
stable per-chart IDs and explicit instance selection, so Docker services and
monitor cgroups are excluded. It performs only HTTP reads and writes a local
JSON file; it does not change Netdata state or launch a background process.

Disk history starts when publication is enabled and uses the existing Netdata
database/retention. Gauges retain the last value between ten-minute scans.
Instance gauges are refreshed only after successful fresh scans. Stopped,
deleted or failed instances stop publishing, and their private charts become
obsolete after twenty minutes without a sample. Historical data still follows
Netdata retention; chart cleanup is not an immediate history purge. At most
200 private charts are allowed. The static host chart retains its last value
if the collector stops; its continuously drawn line is not proof of a new scan.
Check the cron log/snapshot timestamp when diagnosing freshness.

UDP delivery is best-effort, with no application acknowledgement. One small
datagram per metric stays below 1200 bytes; transport errors are logged without
discarding the local snapshot. Do not expose port 8125 on LAN/Tailscale.

### Storage sampling

The `dir` Incus pool does not expose per-instance disk usage in its state API.
Run the collector **on the host**, as a user in `incus-admin`, with Python 3 and
Incus installed:

```bash
cd ~/services/netdata
ionice -c 3 python3 collect-storage.py --statsd
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
command. Unmounted disks are not measured. The native StatsD host chart covers
`/`; extra filesystem paths currently appear only in the JSON/static view.

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
  printf '%s\n' '*/10 * * * * cd "$HOME/services/netdata" && /usr/bin/ionice -c 3 /usr/bin/python3 collect-storage.py --statsd > .collector-last-run.json 2>&1 # factory-incus-storage'
} | crontab -
```

The runtime snapshot `dashboard/incus-storage.json`, lock and last-run log are
ignored by Git. The page marks disk readings older than 18 minutes as stale.
Without `--statsd` the collector only updates that local snapshot. With it,
fresh disk samples are also recorded in Netdata for native charts and history.

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

With native publication enabled, sending seven loopback datagrams (about 500
bytes total) took 0.24 ms; the entire warm scan remained about 1.15 s / 1.17
CPU-seconds. Thirty-second cgroup measurements of the running Netdata service
were 3.61% of one core / 120.0 MiB before, and 2.58% / 95.7 MiB after integration.
The service restarted and its cache/workload varied, so the lower second reading
is not a measured reduction or an isolated estimate of StatsD's cost. No obvious
increase appeared in these short observations; the service limits are unchanged.

Validate the storage accounting/failure behavior and chart transformations:

```bash
python3 test-storage.py
python3 test-dashboard.py
node dashboard/test-metrics.js
node dashboard/test-ui.js
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
- [StatsD collection and chart configuration](https://learn.netdata.cloud/docs/collecting-metrics/statsd)
- [Catppuccin palette](https://github.com/catppuccin/palette)
