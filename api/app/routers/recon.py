from fastapi import APIRouter, HTTPException, Query
from redis import Redis
from rq import Queue

from ..config import settings

router = APIRouter(prefix="/recon", tags=["reconstruction"])

VALID_FILTERS = {"ramp", "shepp-logan", "cosine", "hamming", "hann"}

# The single worker processes jobs serially; cap the pending backlog so the
# public, unauthenticated endpoint can't pile up unbounded CPU work (each job
# can run up to job_timeout=300s).
MAX_PENDING_JOBS = 8


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
    queue = _queue()
    if len(queue) >= MAX_PENDING_JOBS:
        raise HTTPException(429, "Recon queue is busy; try again shortly")
    job = queue.enqueue(
        "app.tasks.reconstruct_phantom",
        n_angles,
        filter_name,
        size,
        job_timeout=300,
        result_ttl=3600,
    )
    return {"job_id": job.id, "status": job.get_status()}
