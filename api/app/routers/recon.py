from fastapi import APIRouter, HTTPException, Query
from redis import Redis
from rq import Queue

from ..config import settings

router = APIRouter(prefix="/recon", tags=["reconstruction"])

VALID_FILTERS = {"ramp", "shepp-logan", "cosine", "hamming", "hann"}


def _queue() -> Queue:
    return Queue("default", connection=Redis.from_url(settings.redis_url))


@router.post("/phantom")
def recon_phantom(
    n_angles: int = Query(180, ge=8, le=720),
    filter_name: str = Query("ramp"),
    size: int = Query(256, ge=64, le=512),
) -> dict:
    """Enqueue a filtered-backprojection demo. Poll /api/jobs/{job_id} for the result."""
    if filter_name not in VALID_FILTERS:
        raise HTTPException(400, f"filter_name must be one of {sorted(VALID_FILTERS)}")
    job = _queue().enqueue(
        "app.tasks.reconstruct_phantom",
        n_angles,
        filter_name,
        size,
        job_timeout=300,
        result_ttl=3600,
    )
    return {"job_id": job.id, "status": job.get_status()}
