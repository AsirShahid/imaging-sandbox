# Architecture & decisions

## Request flow

```
Internet ──TLS──► Nginx Proxy Manager (existing edge, owns the domain)
                        │  http  (shared docker net: nginx-proxy-manager_default)
                        ▼
                  proxy  (internal nginx, no TLS, container name: imaging-proxy)
        ┌───────────────┼─────────────────────┐
        ▼               ▼                     ▼
   /  → ohif    /dicom-web/ → orthanc    /api/ → api
   (viewer)     (GET/HEAD/OPTIONS only)  (FastAPI)
                        │                     │
                        ▼                     ▼
                 postgres (index)        redis ──► worker (recon, metrics)
```

Everything is one origin, so OHIF talks to DICOMweb with **no CORS**.

## Why NPM stays the edge (and there's no Caddy)

The VPS already runs Nginx Proxy Manager fronting many services. Adding a second
public/TLS proxy would mean two things fighting over :443 and two cert stores. So:

- **NPM** = public edge: domain, TLS/Let's Encrypt, HSTS. Unchanged.
- **`proxy` (internal nginx)** = *application* glue only: same-origin path routing
  + the read-only DICOMweb guard. Joins NPM's network; NPM forwards to
  `imaging-proxy:80`.

The app-routing and the security guard live **in this repo**
(`proxy/default.conf`), not in NPM's GUI/database — so they're version-controlled
and reviewable. You *could* express the locations + `limit_except` guard in NPM's
advanced config and drop the `proxy` service, but then the security-critical bit
is GUI state that's easy to lose. Keeping it in-repo is the deliberate choice.

## Security model

- **Public = read-only.** `proxy` rejects every write verb (`POST/PUT/DELETE/PATCH`)
  on `/dicom-web/`. Visitors view; they cannot STOW.
- **Compute API is throttled.** The `/api/` endpoints are unauthenticated and a
  few do real work (recon enqueue, scikit-image metrics), so the proxy applies a
  `limit_req`/`limit_conn` cap and the recon router rejects new jobs once the
  worker backlog hits `MAX_PENDING_JOBS`. This is the same co-tenant-protection
  goal as the `mem_limit`s, enforced for request load instead of memory.
- **Orthanc is never directly public.** Only `/dicom-web/` (reads) is proxied;
  the REST API and Explorer UI are not. The admin port is published on
  `127.0.0.1:8042` → admin/ingest only via SSH tunnel.
- **No DIMSE.** `DicomServerEnabled: false` — no classic C-STORE port to expose.
- **PHI containment.** No public upload path means the box can't accumulate PHI.
  `/api/deid/check` is a teaching/QA tool over curated data; it also flags
  burned-in-pixel risk (metadata scrubbing ≠ pixel scrubbing).
- **Co-tenant isolation.** Don't add an NPM host pointing at Orthanc REST/Explorer.

## Compute: torch/MONAI stays offline (now a choice, not a limit)

The box has 4 ARM vCPUs and ~23 GiB RAM, so PyTorch/MONAI CPU inference *would*
fit. The reason heavy ML still lives in [`offline/`](../offline/) is deliberate,
not a memory constraint:

- **No GPU + shared box.** CPU inference on a 3D volume is slow and CPU-hungry;
  running it for a *public* demo would steal cycles from Immich/Nextcloud/etc.
- **Cleaner integration.** Running inference on your workstation and pushing the
  result back as a **DICOM SEG** gives a standards-compliant overlay in OHIF —
  the most "real radiology" outcome, and a better portfolio artifact than a PNG.

If you later want live inference, the headroom is there: add a dedicated
CPU-inference worker (raise its `mem_limit`) for *private/authenticated* use, or
move ML to a GPU box and keep this VPS as the viewer/PACS front.

### Why CT recon uses phantoms

Filtered backprojection needs **projection (sinogram) data**, which ordinary
DICOM image series don't contain. The demo generates a Shepp-Logan phantom,
forward-projects it (`radon`), then reconstructs (`iradon`) so you can show how
angle count / filter choice trade off against SSIM/PSNR — all CPU-cheap.

### Async, not inline

Reconstruction and volume metrics are CPU-bound and would time out an HTTP
request, so they're enqueued to Redis and run on `worker`. The API returns a
`job_id`; clients poll `/api/jobs/{id}`.

## Resource budget

`mem_limit`s are **co-tenant protection** on a shared 23 GiB box (they cap this
public stack, not the machine):

| Service   | mem_limit | typical |
|-----------|-----------|---------|
| orthanc   | 1g        | ~150–300m |
| postgres  | 512m      | ~50–120m |
| api       | 512m      | ~120m |
| worker    | 2g        | spikes during a job |
| redis     | 256m      | ~20m |
| ohif/proxy| —         | ~20–40m each |

Raise these if you move heavier work on-box; there's RAM to spare.

## Platform note (ARM)

The host is aarch64. All images here are multi-arch with linux/arm64 builds
(verified for `ohif/app` and `orthancteam/orthanc`). When pinning tags for
production, confirm the pinned tag publishes arm64.
