# Imaging Sandbox

A **demo-only** medical-imaging stack: upload/curate DICOM, view it in a browser,
and run small imaging experiments (metadata, de-identification checks, image-quality
metrics, CT reconstruction). Designed to slot behind the existing **Nginx Proxy
Manager** on the VPS.

> ⚠️ **Public datasets only. No clinical data — ever.** The public instance is
> **read-only**: visitors can view and run tools, but cannot upload.

## Stack

| Service   | Role                                                             |
|-----------|-----------------------------------------------------------------|
| `proxy`   | Internal nginx app-router (same-origin paths + read-only guard)  |
| `ohif`    | OHIF v3 web viewer                                               |
| `orthanc` | DICOM server + DICOMweb (Orthanc, Postgres index)               |
| `postgres`| Orthanc index                                                   |
| `api`     | FastAPI: metadata, de-id checks, quality metrics, recon         |
| `worker`  | RQ worker for CPU-bound jobs (recon, volume metrics)            |
| `redis`   | Job queue                                                       |

Heavy ML (torch/MONAI) is **not** in this stack — see [`offline/`](offline/).

## Quick start (local)

```bash
cp .env.example .env        # set a strong POSTGRES_PASSWORD
docker compose up -d --build
```

- Viewer / DICOMweb / API are served same-origin via the `proxy` service
  (published on `127.0.0.1:8088` for local testing): http://localhost:8088
- API docs: http://localhost:8088/api/docs
- Orthanc admin UI (loopback only): http://localhost:8042

Load the curated public demo set (TCIA, CC BY 3.0 — full scrollable CT/MR series):

```bash
./scripts/load_tcia.sh                      # downloads + loads into Orthanc
./scripts/seed_demo_data.py | docker compose exec -T api python -   # small pydicom extras
# or load your own curated files:
./scripts/load_sample_data.sh /path/to/dicom_dir
```

Datasets and attribution: [`docs/DATASETS.md`](docs/DATASETS.md).

## Deploy behind Nginx Proxy Manager

See [`docs/DEPLOY.md`](docs/DEPLOY.md). NPM keeps terminating TLS and owns the
public domain; deploy with the extra file so the proxy joins NPM's network:

```bash
docker compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

## Security model (short version)

- Public traffic is **read-only**: the proxy rejects every DICOMweb write verb.
- Orthanc's admin port is bound to `127.0.0.1` — admin/ingest only via SSH tunnel.
- Orthanc REST/Explorer is never proxied publicly; only `/dicom-web/` (reads) is.
- Full rationale, the ARM/co-tenant notes, and resource budget: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
