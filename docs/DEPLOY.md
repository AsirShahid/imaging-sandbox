# Deploying on the VPS (behind Nginx Proxy Manager)

## Target box (verified)

Oracle Cloud Ampere instance, **aarch64 (ARM64)**: 4 vCPU, ~23 GiB RAM
(~11 GiB free), 193 GB disk (~59 GB free, ~70% used), no swap. Docker 29 +
Compose v5. NPM already runs here as `nginx-proxy-manager-app-1` on network
`nginx-proxy-manager_default`, owning 80/81/443.

Plenty of headroom for this stack. Two consequences of the box being ARM and
shared:

- **ARM images:** the images used here are multi-arch (verified `ohif/app`,
  `orthancteam/orthanc`, nginx, postgres, redis, python all have linux/arm64).
  When you pin tags later, confirm the pinned tag has an arm64 build.
- **Co-tenant:** Immich/Nextcloud/Paperless/etc. share this box, so the compose
  `mem_limit`s cap this public-facing stack rather than the box's real ceiling.

## 1. Get the code and configure

```bash
git clone <your-repo> imaging-sandbox && cd imaging-sandbox
cp .env.example .env
# edit .env: set a strong POSTGRES_PASSWORD
```

## 2. Start the stack (wired to NPM)

```bash
docker compose -f docker-compose.yml -f docker-compose.npm.yml up -d --build
docker compose ps
curl -s localhost:8088/api/health
```

The `docker-compose.npm.yml` overlay attaches the `proxy` service to NPM's
`nginx-proxy-manager_default` network. (Plain `docker compose up -d` works too,
for local testing without NPM.)

## 3. Add the NPM proxy host

NPM keeps terminating TLS for the domain and forwards to the `proxy` container by
name over the shared network. In NPM → **Add Proxy Host**:

- Domain: `imaging.yourdomain`
- Forward Hostname/IP: `imaging-proxy`  ·  Port: `80`
- **Websockets Support: ON**, Block Common Exploits: ON
- SSL tab: request a Let's Encrypt cert, Force SSL + HSTS

No host port is needed for the public path; `127.0.0.1:8088` exists only for
SSH-tunnel testing.

## 4. Keep Orthanc off the public internet

This is the one firewall rule that matters here: the Orthanc admin port is
published on `127.0.0.1:8042` only — never bind it to `0.0.0.0`, and never add an
NPM proxy host that points at the Orthanc REST API or Explorer. The only public
surface is NPM → `imaging-proxy`, which serves OHIF + read-only `/dicom-web/`.

Sanity check after deploy (8042 must NOT appear on a public address):

```bash
ss -tlnp | grep 8042        # expect 127.0.0.1:8042 only
```

## 5. Load curated public data (admin only)

Ingest goes through the loopback admin port, never the public domain:

```bash
# from your laptop:
ssh -L 8042:localhost:8042 vps        # leave open in another shell
./scripts/load_sample_data.sh /path/to/public_dicom
```

Use only properly licensed, already-anonymized public datasets (e.g. TCIA) and
keep their attribution.

## 6. Backups & updates

```bash
./scripts/backup.sh                # pg dump + storage volume tarball
docker compose -f docker-compose.yml -f docker-compose.npm.yml pull
docker compose -f docker-compose.yml -f docker-compose.npm.yml up -d   # after pinning tags
```

## Troubleshooting

- **OHIF shows no studies** → `curl localhost:8088/dicom-web/studies` should
  return JSON; check `docker compose logs orthanc`.
- **Upload returns 403 on the public URL** → expected; that's the read-only
  guard. Ingest via the admin tunnel (step 5).
- **NPM can't reach `imaging-proxy`** → confirm both are on
  `nginx-proxy-manager_default`: `docker network inspect nginx-proxy-manager_default`.
- **Orthanc won't start** → Postgres password mismatch between `.env` and an
  existing `pg_data` volume; `docker compose down -v` only if you can lose data.
