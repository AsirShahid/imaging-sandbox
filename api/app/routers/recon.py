from fastapi import APIRouter, HTTPException, Query

from ..queue import enqueue_capped

router = APIRouter(prefix="/recon", tags=["reconstruction"])

VALID_FILTERS = {"ramp", "shepp-logan", "cosine", "hamming", "hann"}


@router.post("/phantom")
def recon_phantom(
    n_angles: int = Query(180, ge=8, le=720),
    filter_name: str = Query("ramp"),
    size: int = Query(256, ge=64, le=512),
) -> dict:
    """Enqueue a filtered-backprojection demo. Poll /api/jobs/{job_id} for the result."""
    if filter_name not in VALID_FILTERS:
        raise HTTPException(400, f"filter_name must be one of {sorted(VALID_FILTERS)}")
    job = enqueue_capped("app.tasks.reconstruct_phantom", n_angles, filter_name, size)
    return {"job_id": job.id, "status": job.get_status()}
