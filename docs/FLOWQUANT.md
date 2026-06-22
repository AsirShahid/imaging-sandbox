# Phase-contrast (PC) MRI flow quantification

A small, **validated** pipeline that turns phase-contrast MRI into the flow metrics
used to study CSF and blood dynamics — built around the analysis a neurofluidics
study (e.g. idiopathic normal-pressure hydrocephalus, iNPH) actually needs:
the **aqueductal CSF stroke volume** and the flow waveform over the cardiac cycle.

It follows the same discipline as the CT-reconstruction work this sandbox grew from:
build a known ground truth, recover the quantity of interest, and *measure the error*.

## Physics

In a PC acquisition the signal phase is proportional to through-plane velocity,
wrapped into `(-π, π]`:

```
phase = wrap(π · v / VENC)     ⇔     v = phase · VENC / π
```

When `|v| > VENC` the phase wraps and the velocity **aliases**. An optional temporal
phase unwrap recovers it, assuming the true phase changes by `< π` between
cardiac-gated frames.

Flow through a region of interest (e.g. the cerebral aqueduct) is the velocity
integrated over the ROI area, per frame:

```
Q(t) = Σ_ROI v · pixel_area        [µL/s]
```

From `Q(t)`: peak velocity, forward / reverse / net volume, **stroke volume**
(mean of forward and reverse volume per cycle), regurgitant fraction, mean flow.

## Layout (`api/app/flowquant/`)

| File          | Role                                                              |
|---------------|-------------------------------------------------------------------|
| `quantify.py` | Pure-numpy core: phase→velocity, ROI flow, flow metrics.          |
| `phantom.py`  | Digital PC phantom with a **prescribed** stroke volume (truth).   |
| `validate.py` | Sweeps: stroke-volume error vs SNR and vs VENC (mean ± SEM).      |
| `plots.py`    | Matplotlib (Agg) → base64 PNG renderers (flow curve, overlays).   |

The numeric core has no Orthanc/matplotlib dependency, so it is fast to unit-test.

## API

Async jobs (poll `/api/jobs/{job_id}` for results), capped by the shared queue guard:

```bash
# Quantify a ground-truth phantom: returns true vs recovered metrics + plots
curl -X POST "http://localhost:8088/api/flow/demo?venc_cm_s=8&snr=30&stroke_volume_uL=40"

# Aliasing case + temporal unwrap recovery
curl -X POST "http://localhost:8088/api/flow/demo?venc_cm_s=4&snr=40&anti_alias=true"

# Validation sweeps (error vs SNR and VENC, mean ± SEM)
curl -X POST "http://localhost:8088/api/flow/validate?n_seeds=10"
```

Render a phantom series in OHIF:

```bash
docker compose exec -T api python - < scripts/seed_pc_phantom.py
```

## Scope & honesty

- The phantom is **synthetic** — a controllable ground truth, not anatomy. Its value
  is that recovery error is exactly measurable.
- `phase → velocity` is parameterized by `(VENC, scale)`; **vendor phase conventions
  differ**, so real Siemens PC series will need their VENC/scaling confirmed before
  the numbers are trusted.
- Reported normal-vs-iNPH stroke-volume ranges (when shown) are **illustrative
  context, not a clinical readout**.

## Tests

```bash
cd api && pip install -r requirements-dev.txt && pytest tests -q
```
