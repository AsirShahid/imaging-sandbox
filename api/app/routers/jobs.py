from fastapi import APIRouter, HTTPException
from redis import Redis
from rq.exceptions import NoSuchJobError
from rq.job import Job

from ..config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str) -> dict:
    conn = Redis.from_url(settings.redis_url)
    try:
        job = Job.fetch(job_id, connection=conn)
    except NoSuchJobError:
        raise HTTPException(404, "Unknown job id")
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result if job.is_finished else None,
        "error": job.exc_info if job.is_failed else None,
    }
