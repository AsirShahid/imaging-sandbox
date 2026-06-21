from fastapi import APIRouter, HTTPException, Query

from ..orthanc_client import find_instances, get_instance_tags

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("")
def metadata(
    sop_uid: str | None = Query(None, description="SOPInstanceUID"),
    study_uid: str | None = Query(None, description="StudyInstanceUID"),
) -> dict:
    """Simplified DICOM tags for one instance (first match for the given UID)."""
    if not (sop_uid or study_uid):
        raise HTTPException(400, "Provide sop_uid or study_uid")
    ids = find_instances(study_uid=study_uid, sop_uid=sop_uid, limit=1)
    if not ids:
        raise HTTPException(404, "No matching instance in Orthanc")
    return get_instance_tags(ids[0])
