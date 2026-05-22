# Usenet Media Server Guide

A complete guide for setting up a Usenet-based media server stack with Jellyfin and the *arr suite on Proxmox.

---

## What Changed from the Previous Guide

This guide replaces the original Real-Debrid + Zurg setup. Here's what changed and why:

### Real-Debrid → Usenet (nzbdav)
The entire content source layer was replaced. Real-Debrid is a debrid service that caches torrents — it's cheap but dependent on a third-party service, subject to DMCA takedowns, and requires a VPN for torrent indexing. Usenet is a fundamentally different protocol: direct server-to-server transfers over HTTPS, no peers, no swarm, no VPN needed, and files stay available for years.

**Zurg + rclone → nzbdav + nzbdav_rclone**: Zurg was the WebDAV bridge for Real-Debrid. nzbdav is its Usenet equivalent — it receives NZBs from the arrs, streams content from Usenet providers on demand, and exposes it via WebDAV for rclone to mount.

### jellyseerr → seerr
The original `fallenbagel/jellyseerr` image was replaced by `ghcr.io/seerr-team/seerr` — a maintained fork that has continued active development.

### huntarr → neutarr
huntarr was replaced due to a serious security vulnerability discovered by the community — it exposed arr API keys, passwords, and configuration data. Full details: [reddit.com/r/selfhosted/comments/1rckopd](https://www.reddit.com/r/selfhosted/comments/1rckopd/huntarr_your_passwords_and_your_entire_arr_stacks/)

neutarr (`iampuid0/neutarr`) fills the same role — automated hunting for missing and upgradeable content across arr instances.

### Quality profiles
Previously pointed to TRaSH Guides + Notifiarr's paid sync tool. Now maintained as a GitHub repo with a CLI import script — free, no third-party service required. See the [Quality Profiles](#quality-profiles) section.

### Removed services
- **notifiarr** — notifications and TRaSH sync (replaced by the quality profiles repo)
- **jellystat** — Jellyfin statistics (removed, no direct replacement)

### Other changes
- Disk size recommendation: 500 GB → 100 GB (nothing stored locally with Usenet streaming)
- GPU passthrough syntax updated: `lxc.cgroup.devices.allow` → `lxc.cgroup2.devices.allow` (cgroup v2, required on modern Proxmox)
- Jellyfin KnownProxies set to `172.18.0.0/16` so Jellyfin sees real client IPs instead of Caddy's internal address
- Jellyfin plugin setup fully documented for the first time

---

## What is Usenet?

Usenet is a global network of servers that has existed since 1980 — long before torrents. It works like a distributed message board where files are posted as binary attachments and replicated across thousands of servers worldwide. When you download something, you're pulling it directly from a server over HTTPS, not from other users.

### Usenet vs Torrents

| | Usenet | Torrents |
|---|---|---|
| **How it works** | Download from central servers over HTTPS | Peer-to-peer — download from other users |
| **Speed** | Full line speed, always | Depends on how many seeders are online |
| **Privacy** | No peers, no swarm — your IP is never exposed | Your IP is visible to every peer in the swarm |
| **VPN required** | No | Strongly recommended |
| **Retention** | Files stay available for years (3,000+ days on good providers) | Depends on seeders — can disappear overnight |
| **Cost** | ~$30–75/year for a provider | Free (but VPN costs money) |
| **Discovery** | Requires indexers (NZBGeek, DrunkenSlug, etc.) | Public trackers + private trackers |

### What You Need

1. **A Usenet provider** — the server that stores the files. This is your one required paid subscription.
2. **Indexers** — search engines that tell you what's available and generate NZB files (the "pointer" to the content). Some are free, some are a few dollars a year.

**Recommended provider: [Newshosting](https://controlpanel.newshosting.com/signup/index.php?promo=fc7nk)**
- ~$30 for the first year, ~$75/year after
- Unlimited speed, 3,500+ day retention, SSL encrypted, no logs

**Recommended indexers:**

| Indexer | Purpose | Cost | Limits |
|---------|---------|------|--------|
| [DrunkenSlug](https://drunkenslug.com/) ⭐ | General — recommended | ~$30/yr, invite only | Unlimited |
| [NZBgeek](https://nzbgeek.info/) | General — good extra coverage | ~$12/yr, open registration | Unlimited |
| SceneNZBs | Scene releases | Open registration | 400 grabs/day |
| ameNZB | Anime only | Free | 100 grabs/day |
| AnimeTosho (Usenet) | Anime only | Free | 300 API requests/day |

Skip ameNZB and AnimeTosho if you don't watch anime.

---

## How It Works

Content is streamed on demand from Usenet — no files are fully downloaded to disk. The flow:

```
User request
    │
    ▼
Seerr (request management)
    │  adds to arr
    ▼
Radarr / Sonarr  ◄──── Prowlarr (usenet indexers)
    │  sends NZB to nzbdav
    ▼
nzbdav (receives NZB, exposes content via WebDAV)
    │  nzbdav_rclone mounts WebDAV at /mnt/nzbdav
    ▼
/mnt/nzbdav/completed-symlinks/  (symlinks → rclone mount → stream)
    │  arr imports symlinks into library
    ▼
/mnt/jelly/{movies,shows,...}  (symlinks only)
    │
    ▼
Jellyfin reads symlink → rclone mount → nzbdav WebDAV → Usenet stream
```

nzbdav receives NZBs from arr and exposes completed content via WebDAV. The `nzbdav_rclone` sidecar mounts that WebDAV at `/mnt/nzbdav` using a FUSE mount. nzbdav creates symlinks inside the mount pointing to the actual content; arr imports those symlinks into `/mnt/jelly`. Nothing is stored locally — playback streams through the symlink chain at runtime.

---

## Prerequisites

- Proxmox VE server with Intel iGPU (for hardware transcoding)
- Usenet provider account (e.g. Newshosting, Eweka, UsenetExpress)
- Usenet indexer accounts (e.g. NZBGeek, DrunkenSlug) — add these to Prowlarr
- nzbdav account/license
- Domain name with wildcard DNS pointing to your server IP

---

## LXC Setup & GPU Passthrough

### Step 1: Create Ubuntu LXC Container

Run in the Proxmox shell:
```bash
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/ubuntu.sh)"
```

Recommended settings:

| Setting | Value |
|---------|-------|
| OS | Ubuntu 24.04 |
| Container Type | Privileged |
| Disk Size | 100 GB (media stays on Usenet, not local) |
| CPU Cores | 4+ |
| RAM | 8–10 GB |
| IP Address | Static, e.g. 192.168.1.x/24 |

### Step 2: Configure GPU Passthrough

On the Proxmox host, edit the LXC config:
```bash
nano /etc/pve/lxc/<id>.conf
```

Add:
```
lxc.cgroup2.devices.allow: c 226:* rwm
lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir
features: fuse=1,nesting=1
```

Restart the container:
```bash
pct stop <id> && pct start <id>
```

### Step 3: Install Intel Video Drivers (inside the container)

```bash
apt update && apt install -y intel-media-va-driver vainfo
vainfo  # verify output shows decode/encode entrypoints
```

### Step 4: Create User

```bash
adduser --uid 1000 media
chown -R 1000:1000 /opt /mnt
usermod -aG render media
```

Find your render group IDs — these go into the jellyfin `group_add` in the compose:
```bash
getent group video render
```

---

## Docker & Portainer

```bash
# Install Docker
apt update && apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable docker --now

# Install Portainer
docker volume create portainer_data
docker run -d -p 9000:9000 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

Open `http://<your-lxc-ip>:9000` to finish Portainer setup.

---

## Directory Structure

```bash
mkdir -p /mnt/jelly/{movies,movies4k,shows,shows4k,anime}
mkdir -p /mnt/nzbdav
mkdir -p /mnt/downloads
mkdir -p /opt/{jellyfin/config,jellyfin/web,radarr,radarr4k,sonarr,sonarr4k,bazarr,bazarr4k,prowlarr,seerr,nzbdav/config,autosync,neutarr,wizarr/database,caddy/{caddy_data,caddy_config,site}}
chown -R 1000:1000 /opt /mnt
```

`/mnt/nzbdav` is the rclone FUSE mount point. After the stack is running you should see `.ids`, `completed-symlinks`, `content`, and `nzbs` directories there.

---

## rclone Config

The rclone sidecar needs a config file that points at nzbdav's WebDAV. Create `/opt/nzbdav/rclone.conf`:

Generate an obscured password first (use the WebDAV password you set in nzbdav UI → Settings → WebDAV):
```bash
docker run --rm rclone/rclone obscure "<your-webdav-password>"
```

Then create the config:
```ini
[nzbdav]
type = webdav
url = http://nzbdav:3000/
vendor = other
user = <your-webdav-username>
pass = <paste-obscured-password-here>
```

---

## nzbdav Setup

nzbdav acts as both the arr download client and the rclone-mounted content source. After deploying the stack and accessing nzbdav at `http://<your-lxc-ip>:3000`:

1. Configure usenet providers under **Settings → Usenet**
2. Set WebDAV credentials under **Settings → WebDAV** (use these same credentials in `rclone.conf` above)
3. Set **Settings → SABnzbd → Rclone Mount Directory** to `/mnt/nzbdav`
4. Set **Settings → SABnzbd → Rclone Server Host** to `http://nzbdav_rclone:5572` (enables RC notifications so rclone cache invalidates instantly when content changes)
5. Set **Settings → Repairs → Library Directory** to `/mnt/jelly` and enable **Background Repairs**

The arr containers communicate with nzbdav as a SABnzbd download client. When a download completes, nzbdav creates symlinks at `/mnt/nzbdav/completed-symlinks/` pointing into the rclone-mounted content. Arr picks up those symlinks and imports them into `/mnt/jelly`.

---

## Stack Deployment

### Create the Docker network
```bash
docker network create caddy
```

### Deploy via Portainer

Go to **Stacks → Add Stack**, name it `jellysuite`, and paste:

```yaml
name: jellysuite

networks:
  caddy:
    external: true

services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    init: true
    user: 1000:1000
    environment:
      - PGID=1000
      - PUID=1000
      - TZ=America/Chicago
      - transcode_cache_size=25GB
      - JELLYFIN_FFmpeg__timeout=15000000
    group_add:
      - "<video-group-id>"    # run: getent group video
      - "<render-group-id>"   # run: getent group render
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128
      - /dev/dri/card0:/dev/dri/card0
    volumes:
      - /opt/jellyfin/config:/config
      - /var/cache/jellyfin:/cache
      - /mnt:/mnt:rslave
      - /opt/jellyfin/web/config.json:/jellyfin/jellyfin-web/config.json
    ports:
      - "8096:8096"
    restart: unless-stopped
    networks:
      - caddy

  seerr:
    image: ghcr.io/seerr-team/seerr:latest
    init: true
    container_name: seerr
    environment:
      - LOG_LEVEL=debug
      - TZ=America/Chicago
      - PGID=1000
      - PUID=1000
    ports:
      - "5055:5055"
    volumes:
      - /opt/seerr:/app/config
    healthcheck:
      test: wget --no-verbose --tries=1 --spider http://localhost:5055/api/v1/settings/public || exit 1
      start_period: 20s
      timeout: 3s
      interval: 15s
      retries: 3
    restart: unless-stopped
    networks:
      - caddy

  radarr:
    image: ghcr.io/hotio/radarr:release
    container_name: radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /mnt:/mnt:rslave
      - /opt/radarr:/config
    ports:
      - "7878:7878"
    restart: unless-stopped
    networks:
      - caddy

  radarr4k:
    image: ghcr.io/hotio/radarr:release
    container_name: radarr4k
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /mnt:/mnt:rslave
      - /opt/radarr4k:/config
    ports:
      - "7879:7878"
    restart: unless-stopped
    networks:
      - caddy

  sonarr:
    image: ghcr.io/hotio/sonarr:release
    container_name: sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /mnt:/mnt:rslave
      - /opt/sonarr:/config
    ports:
      - "8989:8989"
    restart: unless-stopped
    networks:
      - caddy

  sonarr4k:
    image: ghcr.io/hotio/sonarr:release
    container_name: sonarr4k
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /mnt:/mnt:rslave
      - /opt/sonarr4k:/config
    ports:
      - "8990:8989"
    restart: unless-stopped
    networks:
      - caddy

  prowlarr:
    image: ghcr.io/hotio/prowlarr:release
    container_name: prowlarr
    environment:
      - PUID=1000
      - PGID=1000
    volumes:
      - /mnt:/mnt:rslave
      - /opt/prowlarr:/config
    ports:
      - "9696:9696"
    restart: unless-stopped
    networks:
      - caddy

  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/bazarr:/config
      - /mnt:/mnt:rslave
    ports:
      - "6767:6767"
    restart: unless-stopped
    networks:
      - caddy

  bazarr4k:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr4k
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/bazarr4k:/config
      - /mnt:/mnt:rslave
    ports:
      - "6768:6767"
    restart: unless-stopped
    networks:
      - caddy

  nzbdav:
    image: nzbdav/nzbdav:latest
    container_name: nzbdav
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/nzbdav/config:/config
      - /mnt:/mnt:rshared
    ports:
      - "3000:3000"
    healthcheck:
      test: curl -f http://localhost:3000/health || exit 1
      interval: 1m
      retries: 3
      start_period: 10s
      timeout: 5s
    restart: unless-stopped
    networks:
      - caddy

  nzbdav_rclone:
    image: rclone/rclone:latest
    container_name: nzbdav_rclone
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/nzbdav/rclone.conf:/config/rclone/rclone.conf:ro
      - type: bind
        source: /mnt
        target: /mnt
        bind:
          propagation: shared
    cap_add:
      - SYS_ADMIN
    security_opt:
      - apparmor:unconfined
    devices:
      - /dev/fuse:/dev/fuse:rwm
    depends_on:
      nzbdav:
        condition: service_healthy
        restart: true
    command: >
      mount nzbdav: /mnt/nzbdav
        --uid=1000
        --gid=1000
        --umask=0022
        --allow-other
        --allow-non-empty
        --links
        --use-cookies
        --vfs-cache-mode=full
        --vfs-cache-max-size=30G
        --vfs-cache-max-age=24h
        --vfs-cache-min-free-space=10G
        --vfs-read-ahead=512M
        --vfs-read-chunk-size=32M
        --vfs-read-chunk-size-limit=1G
        --buffer-size=0M
        --dir-cache-time=72h
        --attr-timeout=2h
        --transfers=4
        --no-modtime
        --contimeout=10s
        --timeout=30s
        --low-level-retries=3
        --vfs-read-wait=5s
        --rc
        --rc-addr=0.0.0.0:5572
        --rc-no-auth
    restart: unless-stopped
    networks:
      - caddy

  autosync:
    image: ghcr.io/pukabyte/autosync:latest
    container_name: autosync
    environment:
      - TZ=America/Chicago
      - PGID=1000
      - PUID=1000
    volumes:
      - /opt/autosync/config.yaml:/app/config.yaml
      - /mnt:/mnt:rslave
    ports:
      - "3536:3536"
    restart: unless-stopped
    networks:
      - caddy

  neutarr:
    image: iampuid0/neutarr:latest
    container_name: neutarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/neutarr:/config
    ports:
      - "9705:9705"
    restart: unless-stopped
    networks:
      - caddy

  wizarr:
    image: ghcr.io/wizarrrr/wizarr:latest
    container_name: wizarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
    volumes:
      - /opt/wizarr/database:/data/database
    ports:
      - "5690:5690"
    networks:
      - caddy

  caddy:
    image: caddy:latest
    container_name: caddy
    volumes:
      - /opt/caddy/:/etc/caddy/
      - /opt/caddy/site:/srv
      - /opt/caddy/caddy_data:/data
      - /opt/caddy/caddy_config:/config
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped
    networks:
      - caddy
```

---

## Caddy Configuration

Create `/opt/caddy/Caddyfile`. All internal service references use container names — Caddy resolves them via the shared Docker network.

```caddy
{
  email <your-email>
}

jellyfin.<your-domain> {
  reverse_proxy jellyfin:8096
}

requests.<your-domain> {
  reverse_proxy seerr:5055
}

sonarr.<your-domain> {
  reverse_proxy sonarr:8989
}

sonarr4k.<your-domain> {
  reverse_proxy sonarr4k:8989
}

radarr.<your-domain> {
  reverse_proxy radarr:7878
}

radarr4k.<your-domain> {
  reverse_proxy radarr4k:7878
}

prowlarr.<your-domain> {
  reverse_proxy prowlarr:9696
}

bazarr.<your-domain> {
  reverse_proxy bazarr:6767
}

autosync.<your-domain> {
  reverse_proxy autosync:3536
}

portainer.<your-domain> {
  reverse_proxy portainer:9000
}

invite.<your-domain> {
  reverse_proxy wizarr:5690
}

# nzbdav — only expose the stream viewer and API, block everything else
nzbdav.<your-domain> {
  handle /view/* {
    reverse_proxy nzbdav:3000
  }
  handle /api {
    reverse_proxy nzbdav:3000
  }
  respond 403
}
```

Reload after any edits:
```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## App Configuration

### Arr — General Settings (each arr)

- Settings → General → Security: set authentication to **Forms** and disable for local addresses

### Arr — Root Folders

| Instance | Root Folder |
|----------|------------|
| radarr | `/mnt/jelly/movies` |
| radarr4k | `/mnt/jelly/movies4k` |
| sonarr | `/mnt/jelly/shows` |
| sonarr4k | `/mnt/jelly/shows4k` |

### Arr — Download Client

In each arr: Settings → Download Clients → Add → **SABnzbd** (nzbdav uses the SABnzbd protocol)

| Field | Value |
|-------|-------|
| Name | `nzbdav` |
| Host | `nzbdav` |
| Port | `3000` |
| Use SSL | No |
| API Key | From nzbdav UI → Settings → SABnzbd → API Key |
| Username | leave blank |
| Password | leave blank |
| Category | `radarr` / `radarr4k` / `sonarr` / `sonarr4k` (match to each instance) |
| Priority | Default |

Hit **Test** to verify the connection before saving.

### Prowlarr — Indexers

Add each indexer under **Indexers → Add Indexer**, search by name, and paste your API key. Set the priority on each indexer under its edit screen → Priority field — lower number = searched first.

### Prowlarr → Arr Sync

In Prowlarr: Settings → Apps → Add Application → select the arr type, then fill in:

| Field | Value |
|-------|-------|
| Prowlarr Server | `http://prowlarr:9696` |
| Radarr Server | `http://radarr:7878` |
| API Key | from Radarr → Settings → General |

Repeat for each arr instance. Once saved, Prowlarr automatically pushes all enabled indexers into each arr's indexer list — you don't need to add them in radarr/sonarr separately.

---

## autosync Configuration

autosync propagates media additions across arr instances (e.g. when radarr adds a movie, it also adds it to radarr4k). Create `/opt/autosync/config.yaml`:

```yaml
log_level: INFO
sync_delay: 5s
sync_interval: 2s
webhook_events:
  radarr:
    - MovieAdded
  sonarr:
    - SeriesAdd
instances:
  - name: radarr
    type: radarr
    url: radarr:7878
    api_key: <radarr-api-key>
    root_folder_path: /mnt/jelly/movies
    quality_profile_id: <profile-id>
    search_on_sync: true
    enabled_events:
      - MovieAdded
  - name: radarr4k
    type: radarr
    url: radarr4k:7878
    api_key: <radarr4k-api-key>
    root_folder_path: /mnt/jelly/movies4k
    quality_profile_id: <profile-id>
    search_on_sync: true
    enabled_events:
      - MovieAdded
  - name: sonarr
    type: sonarr
    url: sonarr:8989
    api_key: <sonarr-api-key>
    root_folder_path: /mnt/jelly/shows
    quality_profile_id: <profile-id>
    search_on_sync: false
    enabled_events:
      - SeriesAdd
    season_folder: true
  - name: sonarr4k
    type: sonarr
    url: sonarr4k:8989
    api_key: <sonarr4k-api-key>
    root_folder_path: /mnt/jelly/shows4k
    quality_profile_id: <profile-id>
    search_on_sync: false
    enabled_events:
      - SeriesAdd
    season_folder: true
```

API keys are found in each arr under Settings → General.

---

## Quality Profiles

The `quality-profiles/` folder contains JSON exports of all custom formats and quality profiles, plus two scripts:

| File | Profile(s) |
|------|-----------|
| `radarr.json` + `radarr-customformats.json` | Remux + WEB 1080p |
| `radarr4k.json` + `radarr4k-customformats.json` | WEB 2160p |
| `sonarr.json` + `sonarr-customformats.json` | WEB-1080p (Alternative), [Anime] Remux-1080p |
| `sonarr4k.json` + `sonarr4k-customformats.json` | WEB-2160p (Alternative) |

### Exporting (keeping the files up to date)

Run this on your server any time you make changes in the arr UIs:

```bash
python3 quality-profiles/export.py
```

It will prompt for each API key and overwrite the JSON files with the current live state.

### Importing (on a new server)

With your stack running:

```bash
git clone https://github.com/beanbaganalytica/arr-quality-profiles
python3 arr-quality-profiles/import.py
```

Both scripts prompt for API keys — find them at **Settings → General → Security → API Key** in each arr. The import script remaps custom format IDs automatically so they match the new instance.

### Keeping profiles in sync

After making changes in the arr UIs, export and push:

```bash
cd /opt/quality-profiles
python3 export.py
git add -A && git commit -m "update profiles"
git push
```

---

## Jellyfin Setup

### Libraries

Add libraries pointing to these folders:

| Library | Path |
|---------|------|
| Movies | `/mnt/jelly/movies` |
| Movies 4K | `/mnt/jelly/movies4k` |
| TV Shows | `/mnt/jelly/shows` |
| TV Shows 4K | `/mnt/jelly/shows4k` |
| Anime | `/mnt/jelly/anime` |

### Hardware Acceleration

Dashboard → Playback → Transcoding:
- **Hardware acceleration**: VAAPI
- **VA API Device**: `/dev/dri/renderD128`
- **Enable hardware decoding**: H.264, HEVC, VC1, VP8, VP9, MPEG2
- **Enable hardware encoding**: on
- **Enable tonemapping**: on (algorithm: bt2390)
- **Allow encoding in HEVC**: off
- **Do NOT enable trickplay hardware acceleration** — trickplay scans require reading every file, which hammers the nzbdav FUSE mount and wastes Usenet bandwidth

### Networking

Dashboard → Networking:
- **Known proxies**: `172.18.0.0/16` — trusts any container on the caddy Docker network as a proxy, so Jellyfin sees real client IPs instead of Caddy's internal address

### Plugins

Add these plugin repositories first under Dashboard → Plugins → Repositories:

| Name | URL |
|------|-----|
| Intro Skipper | `https://intro-skipper.org/manifest.json` |
| Streamyfin | `https://raw.githubusercontent.com/streamyfin/jellyfin-plugin-streamyfin/main/manifest.json` |
| Paradox | `https://www.iamparadox.dev/jellyfin/plugins/manifest.json` |

Then install these plugins from Dashboard → Plugins → Catalog:

| Plugin | Source | Purpose |
|--------|--------|---------|
| **Intro Skipper** | Intro Skipper repo | Auto-detects and skips intros, credits, recaps, previews |
| **Trakt** | Jellyfin Stable | Syncs watched status with Trakt |
| **AniDB** | Jellyfin Stable | Anime metadata (localized titles, Japanese Romaji) |
| **Streamyfin** | Streamyfin repo | Companion plugin for the Streamyfin mobile app |
| **File Transformation** | Paradox repo | Required dependency for Intro Skipper |
| **Home Screen Sections** | Paradox repo | Custom home screen layout sections |
| **Media Bar** | Paradox repo | Cinematic media bar on the home screen |
| **Open Movie Database (OMDb)** | Jellyfin Stable | Additional movie metadata |
| **Studio Images** | Jellyfin Stable | Studio logo images |

### Plugin Configuration

**AniDB**
- Title preference: Localized
- Original title preference: Japanese Romaji
- Max genres: 5, tidy genre list: on

**Intro Skipper**
- Scan: intros, credits, recaps, previews — all on
- Skip first episode intro: on; Skip first episode intro (anime): off
- Uses chapter markers + silence detection + black frames

**Trakt**
- After installing, authenticate your account
- `PostSetWatched`: on — marks items watched on Trakt when you do in Jellyfin
- `SkipWatchedImportFromTrakt`: off — imports your Trakt watch history into Jellyfin
- Scrobble: off (marks watched on completion only, not during playback)

---

## Common Operations

```bash
# Restart a container
docker restart <container-name>

# View logs
docker logs -f <container-name>

# Check all container status
docker ps -a

# Update all images and redeploy
# → Use Portainer UI: Stacks → jellysuite → Pull and redeploy
```
