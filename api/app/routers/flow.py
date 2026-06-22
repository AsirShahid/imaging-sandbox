"""Phase-contrast MRI CSF/blood flow quantification (async, demo-only).

Quantifies aqueductal CSF stroke volume and the flow waveform from a phase-contrast
acquisition. Endpoints synthesize a ground-truth phantom so the analysis is runnable
and verifiable with no patient data; the same quantifier ingests real PC-MRI series.
"""
from fastapi import APIRouter, Query

from ..queue import enqueue_capped

router = APIRouter(prefix="/flow", tags=["flow"])


@router.post("/demo")
def flow_demo(
    venc_cm_s: float = Query(8.0, gt=0, description="Velocity encoding (cm/s)"),
    snr: float = Query(30.0, ge=0, description="Magnitude SNR (0 = noiseless)"),
    stroke_volume_uL: float = Query(40.0, gt=0, description="Ground-truth ASV (µL)"),
    heart_rate_bpm: float = Query(60.0, gt=0),
    anti_alias: bool = Query(False, description="Temporal phase unwrap before decode"),
    seed: int = Query(0, ge=0),
) -> dict:
    """Enqueue a CSF-flow quantification demo. Poll /api/jobs/{job_id} for the result."""
    job = enqueue_capped(
        "app.tasks.quantify_pc_flow",
        venc_cm_s,
        snr,
        stroke_volume_uL,
        heart_rate_bpm,
        anti_alias,
        seed,
    )
    return {"job_id": job.id, "status": job.get_status()}


@router.post("/validate")
def flow_validate(
    n_seeds: int = Query(10, ge=1, le=50, description="Realizations per sweep point"),
) -> dict:
    """Enqueue the validation sweeps (error vs SNR and VENC). Poll /api/jobs/{job_id}."""
    job = enqueue_capped("app.tasks.quantify_pc_validate", n_seeds, job_timeout=600)
    return {"job_id": job.id, "status": job.get_status()}
