# Imaging Sandbox

A **demo-only** medical-imaging stack: upload/curate DICOM, view it in a browser,
and run small imaging experiments (metadata, de-identification checks, image-quality
metrics, CT reconstruction, phase-contrast CSF/blood-flow quantification). Designed
to slot behind the existing **Nginx Proxy Manager** on the VPS.

> ⚠️ **Public datasets only. No clinical data — ever.** The public instance is
> **read-only**: visitors can view and run tools, but cannot upload.

## Stack

| Service   | Role                                                             |
|-----------|-----------------------------------------------------------------|
| `proxy`   | Internal nginx app-router (same-origin paths + read-only guard)  |
| `ohif`    | OHIF v3 web viewer                                               |
| `orthanc` | DICOM server + DICOMweb (Orthanc, Postgres index)               |
| `postgres`| Orthanc index                                                   |
| `api`     | FastAPI: metadata, de-id checks, quality metrics, recon, flow    |
| `worker`  | RQ worker for CPU-bound jobs (recon, PC-MRI flow quant)         |
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

**OpenNeuro / BIDS NIfTI data (e.g. ds000030).** The sandbox ships with a NIfTI-to-DICOM
bridge that converts BIDS T1w images into scrollable DICOM series and pushes them into
Orthanc — making them viewable in OHIF and queryable through the same DICOMweb pipeline.

```bash
# Convert and upload a BIDS dataset to Orthanc
./scripts/nifti_to_orthanc.py /path/to/bids_dir --limit 5 --label public

# Generate QC images from T1w NIfTI files
./scripts/qc_t1w.py /path/to/sub-XXX_T1w.nii.gz [output.png]
./scripts/qc_t1w.py --batch /path/to/bids_dir /output/dir 10
```

The public instance currently serves **265 T1w subjects** from OpenNeuro ds000030
(UCLA CNP, CC0) alongside the TCIA demo set — all browsable in OHIF.

**Local/admin-only data (e.g. ADNI).** Non-redistributable data can live on the
box for your own experiments without ever reaching the public edge:
`./scripts/load_adni.sh /path/to/ADNI_export_dir` ingests over the admin tunnel
and labels each study `private`; the guard then keeps `private` studies off the
public DICOMweb. ADNI's DUA forbids redistribution — never put it on the public
instance. See [`docs/DATASETS.md`](docs/DATASETS.md) and the private-data guard
in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Datasets and attribution: [`docs/DATASETS.md`](docs/DATASETS.md).

## Phase-contrast CSF/blood-flow quantification

A validated PC-MRI flow pipeline (aqueductal CSF **stroke volume**, flow waveform,
peak velocity) with a digital ground-truth phantom so accuracy is measurable —
see [`docs/FLOWQUANT.md`](docs/FLOWQUANT.md).

```bash
curl -X POST "http://localhost:8088/api/flow/demo?venc_cm_s=8&snr=30&stroke_volume_uL=40"
curl -X POST "http://localhost:8088/api/flow/validate?n_seeds=10"   # error vs SNR/VENC
docker compose exec -T api python - < scripts/seed_pc_phantom.py    # render in OHIF
```

## Tests

```bash
cd api && pip install -r requirements-dev.txt && pytest tests -q   # also run in CI
```

## Deploy behind Nginx Proxy Manager

See [`docs/DEPLOY.md`](docs/DEPLOY.md). NPM keeps terminating TLS and owns the
public domain; deploy with the extra file so the proxy joins NPM's network:

```bash
docker compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

## Security model (short version)

- DICOMweb is **read-only**: the proxy rejects every DICOMweb write verb.
- The `/api/` compute endpoints are unauthenticated but **rate-limited** at the
  proxy, and recon jobs are capped by queue depth — so the public surface can't
  exhaust the worker or starve co-tenants.
- Orthanc's admin port is bound to `127.0.0.1` — admin/ingest only via SSH tunnel.
- Orthanc REST/Explorer is never proxied publicly; only `/dicom-web/` (reads) is.
- Full rationale, the ARM/co-tenant notes, and resource budget: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
