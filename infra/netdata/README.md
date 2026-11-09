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

## References

- [Official Docker installation](https://learn.netdata.cloud/docs/netdata-agent/installation/docker)
- [LXC/Incus collection](https://www.netdata.cloud/integrations/data-collection/containers-and-vms/lxc-containers/)
- [Database configuration](https://learn.netdata.cloud/docs/netdata-agent/configuration/database)
