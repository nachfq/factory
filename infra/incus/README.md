# Recreate the Incus host and agent image

This is the working Ubuntu 24.04 amd64 recipe captured from homelab on
2026-11-09. Run the host setup on a fresh server, from this repository's root.
The existing names (`pilot`, `agent-pilot`, `pilot-private`) remain because the
current image builder and `agent-env` use them.

## Install Incus

The recorded packages are Incus **6.0.7**, version
`1:6.0.7-ubuntu24.04-202610301755`, from Zabbly's **6.0 LTS** repository.
The source file below follows that LTS channel, so a later install can receive
a newer 6.0.x release. Incus 6.0.0 is unsuitable: its image unpacker skips
directories named `dev`, including `/home/dev` (upstream issue
[lxc/incus#815](https://github.com/lxc/incus/issues/815), fixed in 6.0.1).

Follow the [Zabbly repository instructions](https://github.com/zabbly/incus#installation).
For the Ubuntu 24.04 amd64 host used here:

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates gnupg uidmap iptables
curl -fsSL https://pkgs.zabbly.com/key.asc -o /tmp/zabbly-incus.asc
gpg --show-keys --fingerprint /tmp/zabbly-incus.asc
```

The signing-key fingerprint used by this setup is
`4EFC590696CB15B87C73A3AD82CC8797C838DCFD`. After verifying it:

```bash
sudo install -d -m 755 /etc/apt/keyrings
sudo install -m 644 /tmp/zabbly-incus.asc /etc/apt/keyrings/zabbly.asc
sudo install -m 644 infra/incus/zabbly-incus-lts-6.0.sources /etc/apt/sources.list.d/
sudo apt-get update
sudo apt-get install -y incus incus-client incus-ui-canonical
sudo usermod -aG incus-admin "$USER"
```

Log out and back in to activate group membership. The host's unprivileged ID
allocation has this entry in **both** `/etc/subuid` and `/etc/subgid`:

```text
root:1000000:1000000000
```

On a fresh host without that allocation, the equivalent command is:

```bash
sudo usermod --add-subuids 1000000-1000999999 --add-subgids 1000000-1000999999 root
sudo systemctl restart incus.service
incus admin init --minimal
```

Inspect existing allocations first when using a server that already has
containers. The non-root login user's own subordinate range is independent.

## Restore storage, network and profile

These files contain only writable configuration, without instance references
or generated IDs. The `dir` pool stores data on the OS filesystem at
`/var/lib/incus/storage-pools/pilot`; it does not use the media disks.

```bash
incus storage create pilot dir < infra/incus/storage-pilot.yaml
incus network acl create pilot-private < infra/incus/acl-pilot-private.yaml
incus network create incusbr0 --type bridge < infra/incus/network-incusbr0.yaml
incus profile create agent-pilot
incus profile edit agent-pilot < infra/incus/profile-agent-pilot.yaml
```

The bridge is `10.77.0.1/24`, with IPv4 NAT and no IPv6 subnet. The ACL blocks
outbound connections to the listed private ranges and allows host-to-guest SSH.
It is not a guarantee of layer-2 isolation between guests on the same bridge.
If this subnet conflicts with another network, change it consistently in the
bridge, ACL and Docker service below.

The profile uses unprivileged containers, separate UID/GID mappings, no host
home/socket mounts, a 2-CPU cap, a 2 GiB RAM cap and manual startup. Those limits
do not reserve resources. `security.nesting` is normally false; only the fresh
image builder enables it temporarily for tool setup.

## Docker coexistence, when applicable

Homelab also runs Docker. Docker's forwarding policy initially blocked Incus
internet access. For hosts using its iptables `DOCKER-USER` chain, install the
same narrowly scoped rules we use there:

```bash
sudo install -m 644 infra/incus/incus-pilot-network.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now incus-pilot-network.service
```

The service adds bridge egress and established return traffic, starts after
Docker, follows Docker restarts and removes only its own rules when stopped.
It requires Docker; omit this step on a host without Docker. Incus's ACL remains
responsible for restricting guest destinations.

## Optional web UI over Tailscale

On a host that already has Tailscale, use that host's own Tailscale IPv4 address:

```bash
sudo install -d /etc/systemd/system/incus.service.d
sudo install -m 644 infra/incus/20-web-ui.conf /etc/systemd/system/incus.service.d/
sudo systemctl daemon-reload
sudo systemctl restart incus.service
incus config set core.https_address YOUR_TAILSCALE_IP:8443
```

Visit `https://YOUR_TAILSCALE_IP:8443/ui/`. In the UI's TLS setup, generate and
download a browser certificate, trust its `.crt` on this host, and import its
`.pfx` in the laptop browser:

```bash
incus config trust add-certificate /path/to/incus-ui.crt
```

Browser certificates, private keys, trust-store entries and login credentials
are generated separately on each installation and are not stored in this repo.
The host's SSH login and Tailscale enrollment are also machine-specific.

## Build the base image

Factory installs the tools and agent defaults; the selected dotfiles checkout
supplies editor/shell configuration. Both source commits must already be pushed,
because the builder downloads them from GitHub.

From a laptop with Factory and dotfiles checkouts:

```bash
cd /path/to/factory
dotfiles_revision=$(git -C ~/dotfiles rev-parse HEAD)
factory_revision=$(git rev-parse HEAD)
ssh user@newserver "bash -s -- $dotfiles_revision $factory_revision" < infra/incus/build-agent-image.sh
```

The script also runs directly on the Incus host with the same two arguments.
An optional third argument selects another public GitHub HTTPS dotfiles repository;
the default is `https://github.com/nachfq/dotfiles.git`. That checkout should provide
`apply.sh apply` for configuration and `apply.sh plugins` for editor dependencies.
Pinned dotfiles revisions with the previous `setup-agent.sh` interface also work.

It creates a fresh Ubuntu 24.04 builder, checks out both pinned sources, installs
Factory's tools and applies the selected dotfiles,
removes credentials/instance identity, stops it and publishes private aliases:

- `agent-base`, the latest successful build;
- `agent-base-DATE-DOTFILES_SHA-FACTORY_SHA`, an immutable build name.

To test a candidate before replacing `agent-base`, set `AGENT_IMAGE_PROMOTE=0`
on the host command (`ssh user@newserver "AGENT_IMAGE_PROMOTE=0 bash -s -- ..."`).
The script publishes only the immutable alias. After testing a container launched
from that alias, promote its fingerprint:

```bash
incus image alias delete agent-base
incus image alias create agent-base FINGERPRINT
```

The image records both complete source revisions in its properties. A failed
builder remains for diagnosis; a successful builder is deleted. Existing working
containers are never used as image builders.

The previous homelab image has fingerprint
`b87b17504ba3faccd5d650660031bd2821708fe47f59b4cad2081f1a6cfc7906`, built from
dotfiles `4db3a67cde6cdb10055813a0433ec13b8a07e659`, with alias
`agent-base-20261106-4db3a67c`. It predates this Factory migration.

This recipe rebuilds the environment; it does not promise identical bytes:
the upstream Ubuntu image and tools installed as `latest`/LTS can change.
To keep an exact copy of an existing clean base image, export that image too:

```bash
mkdir -p ~/image-backups
incus image export agent-base ~/image-backups/agent-base
```

Keep the exported files outside Git. On the new host, `incus image import`
accepts those files and `--alias agent-base` to restore the original image.

## Verification and historical steps

```bash
incus version
incus storage show pilot
incus network show incusbr0
incus network acl show pilot-private
incus profile show agent-pilot
incus image info agent-base
```

The historical [November 6 upgrade script](history/update-incus-host-2026-11-06.sh)
is retained as a record of migrating the original Ubuntu package to Zabbly 6.0.7.
It requires the separately staged `.deb` files and manifests used that day;
those temporary downloads were removed after installation. Use the repository
installation above to set up a fresh host.
