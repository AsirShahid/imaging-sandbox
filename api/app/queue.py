"""Shared RQ queue helpers — one place for the public job-backlog cap.

The /api compute endpoints are public and unauthenticated, and a single worker
processes jobs serially (each up to job_timeout seconds). Cap the pending backlog
so the surface can't pile up unbounded CPU work; this complements the proxy-level
rate limit. Both recon and flow enqueue through here so the cap lives in one spot.
"""
from __future__ import annotations

from fastapi import HTTPException
from redis import Redis
from rq import Queue
from rq.job import Job

from .config import settings

MAX_PENDING_JOBS = 8


def get_queue() -> Queue:
    return Queue("default", connection=Redis.from_url(settings.redis_url))


def enqueue_capped(
    func_path: str,
    *args: object,
    job_timeout: int = 300,
    result_ttl: int = 3600,
) -> Job:
    """Enqueue a worker job, rejecting with HTTP 429 when the backlog is full."""
    queue = get_queue()
    if len(queue) >= MAX_PENDING_JOBS:
        raise HTTPException(429, "Job queue is busy; try again shortly")
    return queue.enqueue(
        func_path, *args, job_timeout=job_timeout, result_ttl=result_ttl
    )
