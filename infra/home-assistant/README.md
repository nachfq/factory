# Home Assistant in Incus

A fresh Ubuntu 24.04 system container runs the official Home Assistant Docker
image with Compose. It uses no agent image, dotfiles, agent credentials or
project tooling. Docker and the service start automatically. Incus limits it to
2 CPUs, 2 GiB RAM and up to 1 GiB additional host swap.

## Network and instance

Run these on the Incus host from the Factory checkout. Set `LAN_INTERFACE` to
the wired interface connected to the device LAN; adjust the `pilot` storage
pool in `profile.yaml` for another host.

```bash
LAN_INTERFACE=YOUR_LAN_INTERFACE
incus network create home-lan --type=macvlan "parent=$LAN_INTERFACE"
incus profile create home-assistant
incus profile edit home-assistant < infra/home-assistant/profile.yaml
incus launch images:ubuntu/24.04 home-assistant -p home-assistant \
  -c user.factory.service=home-assistant -c user.factory.monitor=true
```

The guest obtains its own LAN address through the router's DHCP. Docker's host
network mode refers to this guest, allowing local multicast discovery. Macvlan
cannot communicate directly with the physical host, so the profile's Incus TCP
proxy connects host loopback port 8123 to guest loopback port 8123. This does not
reconfigure the physical host's interface or the isolated agents' network.

## Install in the fresh guest

Copy this directory to `/opt/home-assistant` inside the guest with `incus file
push` or a tar stream, then run as guest root:

```bash
cd /opt/home-assistant
bash install-docker.sh
mkdir -m 700 config
cp configuration.yaml.example config/configuration.yaml
printf '[]\n' > config/automations.yaml
printf '{}\n' > config/scripts.yaml
printf '[]\n' > config/scenes.yaml
printf 'TZ=UTC\n' > .env  # Set the local time zone.
chmod 600 .env
docker compose config --quiet
docker compose up -d
```

Configuration, accounts, integrations and the database persist under
`/opt/home-assistant/config`, outside the Docker container. This directory and
`.env` remain private and untracked. Access uses plain TCP forwarding rather than
an HTTP reverse proxy, so Home Assistant needs no trusted-proxy HTTP settings. No physical-host
USB, Bluetooth or other device passthrough is configured.

## Access and onboarding

The local URL is `http://GUEST_LAN_IP:8123`. For tailnet access, run on the host:

```bash
tailscale serve --bg --tcp=8123 tcp://127.0.0.1:8123
tailscale serve status
```

Open `http://HOSTNAME:8123` through Tailscale. This adds a separate TCP listener
without changing the existing `/factory` routes or router port mappings. The
owner creates their account and password in the onboarding interface, then
confirms discovered integrations or links the relevant manufacturer accounts.
Devices already in Google Home are not automatically imported as a collection.

With the updated Netdata collectors, `user.factory.monitor=true` includes the
service in the existing resource dashboard without making it an `agent-env`.

## Operations

```bash
incus exec home-assistant -- sh -c 'cd /opt/home-assistant && docker compose ps'
incus exec home-assistant -- sh -c 'cd /opt/home-assistant && docker compose logs --tail=60'
incus exec home-assistant -- sh -c 'cd /opt/home-assistant && docker compose pull && docker compose up -d'
incus stop home-assistant --timeout 90
incus start home-assistant
```

Updates are explicit. Before updating, use Home Assistant's backup feature or
take a consistent backup of the config directory while the service is stopped.
Docker allows up to 60 seconds for a clean database shutdown. Incus host shutdown
allows the guest 90 seconds. The app's Docker `privileged` setting follows its
official installation; the outer Incus container remains unprivileged.

Sources: [Home Assistant Container](https://www.home-assistant.io/installation/linux/#install-home-assistant-container),
[Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[Docker in Incus](https://linuxcontainers.org/incus/docs/main/faq/),
[Incus macvlan](https://linuxcontainers.org/incus/docs/main/reference/network_macvlan/).
