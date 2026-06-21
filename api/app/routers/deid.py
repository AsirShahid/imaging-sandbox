from fastapi import APIRouter, HTTPException, Query

from ..orthanc_client import find_instances, get_instance_tags

router = APIRouter(prefix="/deid", tags=["de-identification"])

# Subset of DICOM PS3.15 Basic Profile tags that commonly carry PHI.
PHI_TAGS = {
    "PatientName", "PatientID", "PatientBirthDate", "PatientSex", "PatientAge",
    "PatientAddress", "PatientTelephoneNumbers", "OtherPatientIDs",
    "OtherPatientNames", "EthnicGroup", "ReferringPhysicianName",
    "PerformingPhysicianName", "NameOfPhysiciansReadingStudy", "OperatorsName",
    "RequestingPhysician", "InstitutionName", "InstitutionAddress",
    "InstitutionalDepartmentName", "StationName", "DeviceSerialNumber",
    "AccessionNumber", "StudyID",
}

# SOP classes where PHI is frequently burned into the pixels (text overlays).
BURNED_IN_RISK = {
    "1.2.840.10008.5.1.4.1.1.7": "Secondary Capture",
    "1.2.840.10008.5.1.4.1.1.6.1": "Ultrasound",
    "1.2.840.10008.5.1.4.1.1.3.1": "Ultrasound Multi-frame",
    "1.2.840.10008.5.1.4.1.1.77.1.4": "VL Photographic",
}


@router.get("/check")
def check(
    sop_uid: str | None = Query(None, description="SOPInstanceUID"),
    study_uid: str | None = Query(None, description="StudyInstanceUID"),
) -> dict:
    """Residual-PHI report for one instance: populated PHI tags + a burned-in
    pixel-text warning for risky SOP classes. A teaching/QA tool, not a scrubber."""
    if not (sop_uid or study_uid):
        raise HTTPException(400, "Provide sop_uid or study_uid")
    ids = find_instances(study_uid=study_uid, sop_uid=sop_uid, limit=1)
    if not ids:
        raise HTTPException(404, "No matching instance in Orthanc")
    tags = get_instance_tags(ids[0])

    populated = {name: tags[name] for name in PHI_TAGS if str(tags.get(name, "")).strip()}
    sop_class = tags.get("SOPClassUID", "")
    burned_flag = str(tags.get("BurnedInAnnotation", "")).upper() == "YES"
    pixel_risk = sop_class in BURNED_IN_RISK or burned_flag

    notes = []
    if pixel_risk:
        label = BURNED_IN_RISK.get(sop_class, "flagged BurnedInAnnotation")
        notes.append(
            f"Pixel PHI risk ({label}): tag scrubbing does NOT remove text burned "
            "into the image. Review/redact pixels separately."
        )
    return {
        "clean": not populated and not pixel_risk,
        "phi_tags_present": populated,
        "pixel_phi_risk": pixel_risk,
        "sop_class_uid": sop_class,
        "notes": notes,
    }
