"""Thin Orthanc REST helpers. The API reaches Orthanc on the internal network
(no auth needed there); the public read-only guard is enforced at the proxy."""
from __future__ import annotations

import httpx

from .config import settings


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.orthanc_url, timeout=settings.request_timeout)


def find_instances(
    study_uid: str | None = None,
    series_uid: str | None = None,
    sop_uid: str | None = None,
    limit: int = 25,
) -> list[str]:
    """Return Orthanc internal instance IDs matching the given DICOM UIDs."""
    query: dict[str, str] = {}
    if study_uid:
        query["StudyInstanceUID"] = study_uid
    if series_uid:
        query["SeriesInstanceUID"] = series_uid
    if sop_uid:
        query["SOPInstanceUID"] = sop_uid
    with _client() as c:
        r = c.post("/tools/find", json={"Level": "Instance", "Query": query, "Limit": limit})
        r.raise_for_status()
        return r.json()


def get_instance_file(orthanc_id: str) -> bytes:
    with _client() as c:
        r = c.get(f"/instances/{orthanc_id}/file")
        r.raise_for_status()
        return r.content


def get_instance_tags(orthanc_id: str) -> dict:
    with _client() as c:
        r = c.get(f"/instances/{orthanc_id}/simplified-tags")
        r.raise_for_status()
        return r.json()
