"""Seed Orthanc with a synthetic phase-contrast (PC) MRI flow series.

Generates the digital flow phantom and writes it as a DICOM study (magnitude +
phase series) so it renders in OHIF and can be pulled back by the flow quantifier.
This is a *synthetic* series — no patient data — and a best-effort DICOM writer
(Orthanc is lenient); the canonical, verifiable output is the /api/flow analysis.

Run inside the api container (it has pydicom + numpy + httpx + egress to Orthanc):
    docker compose exec -T api python - < scripts/seed_pc_phantom.py
"""
from __future__ import annotations

import os

import httpx
import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    MRImageStorage,
    generate_uid,
)

from app.flowquant.phantom import make_pc_phantom

ORTHANC = os.environ.get("ORTHANC_URL", "http://orthanc:8042")


def _base(study_uid, series_uid, frame, matrix, modality_desc, pixel_mm):
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = MRImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = MRImageStorage
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.Modality = "MR"
    ds.PatientID = "PHANTOM-PCFLOW"
    ds.PatientName = "Synthetic^PCFlow"
    ds.SeriesDescription = f"PC-MRI {modality_desc} (synthetic)"
    ds.InstanceNumber = frame + 1
    ds.Rows, ds.Columns = matrix, matrix
    ds.PixelSpacing = [f"{pixel_mm:.4f}", f"{pixel_mm:.4f}"]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    return ds


def _post(ds):
    from io import BytesIO

    buf = BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    r = httpx.post(f"{ORTHANC}/instances", content=buf.getvalue(), timeout=60)
    return r.status_code in (200, 201)


def main() -> None:
    ph = make_pc_phantom()
    n = ph["params"]["matrix"]
    pixel = ph["pixel_spacing_mm"][0]
    study_uid = generate_uid()
    mag_uid, phase_uid = generate_uid(), generate_uid()

    # Magnitude series: scale to uint16.
    mag = ph["magnitude"]
    mag_u16 = (mag / mag.max() * 4095.0).astype(np.uint16)

    # Phase series: store as int16 with RescaleSlope/Intercept -> radians.
    phase = ph["phase"]  # radians in (-pi, pi]
    slope = np.pi / 2048.0
    phase_i16 = np.clip(np.round(phase / slope), -2048, 2047).astype(np.int16)

    n_frames = mag.shape[0]
    loaded = 0
    for i in range(n_frames):
        m = _base(study_uid, mag_uid, i, n, "magnitude", pixel)
        m.PixelRepresentation = 0
        m.PixelData = mag_u16[i].tobytes()
        loaded += _post(m)

        p = _base(study_uid, phase_uid, i, n, "phase", pixel)
        p.PixelRepresentation = 1
        p.RescaleSlope = f"{slope:.8f}"
        p.RescaleIntercept = "0"
        p.RescaleType = "rad"
        p.PixelData = phase_i16[i].tobytes()
        loaded += _post(p)

    print(f"seeded {loaded} instances ({n_frames} frames x 2 series)")
    print(f"  VENC={ph['venc_cm_s']} cm/s  true stroke volume="
          f"{ph['true_metrics']['stroke_volume_uL']:.1f} uL")


if __name__ == "__main__":
    main()
