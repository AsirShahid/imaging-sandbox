#!/usr/bin/env python3
"""Convert NIfTI T1w images to DICOM and upload to Orthanc.

Reads a BIDS directory, converts T1w NIfTI files to DICOM series with proper
metadata, and POSTs them to Orthanc via the admin REST API.

Usage:
    python nifti_to_orthanc.py <bids_dir> [--limit N] [--orthanc URL] [--label LABEL]

Examples:
    # Convert first 5 subjects (test)
    python nifti_to_orthanc.py /srv/neurodata/openneuro/raw/ds000030 --limit 5

    # Full batch
    python nifti_to_orthanc.py /srv/neurodata/openneuro/raw/ds000030 --label public

    # Private data
    python nifti_to_orthanc.py /path/to/private/bids --label private
"""

import argparse
import glob
import os
import sys
from io import BytesIO

import httpx
import nibabel as nib
import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid


def load_participants(bids_dir):
    """Load participants.tsv into a dict keyed by participant_id."""
    tsv_path = os.path.join(bids_dir, "participants.tsv")
    participants = {}
    if not os.path.exists(tsv_path):
        return participants
    with open(tsv_path) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            vals = line.strip().split("\t")
            row = dict(zip(header, vals))
            pid = row.get("participant_id", "")
            if pid.startswith("sub-"):
                pid = pid[4:]
            participants[pid] = row
    return participants


def nifti_to_dicom_slices(nifti_path, patient_name, patient_id, study_desc="OpenNeuro ds000030"):
    """Convert a 3D NIfTI to a list of DICOM file bytes (one per axial slice)."""
    img = nib.load(nifti_path)
    data = img.get_fdata()
    affine = img.affine
    zooms = img.header.get_zooms()

    study_uid = generate_uid()
    series_uid = generate_uid()

    # Normalize to uint16
    dmax = data.max()
    if dmax > 0:
        slope = dmax / 65535.0
        data_u16 = (data / slope).astype(np.uint16)
    else:
        slope = 1.0
        data_u16 = np.zeros_like(data, dtype=np.uint16)

    rows, cols = data.shape[0], data.shape[1]
    n_slices = data.shape[2]
    pixel_spacing = [float(zooms[0]), float(zooms[1])]
    slice_thickness = float(zooms[2]) if len(zooms) > 2 else 1.0

    # Direction cosines from affine
    row_cosine = affine[:3, 0] / np.linalg.norm(affine[:3, 0])
    col_cosine = affine[:3, 1] / np.linalg.norm(affine[:3, 1])
    image_orientation = [
        float(row_cosine[0]), float(row_cosine[1]), float(row_cosine[2]),
        float(col_cosine[0]), float(col_cosine[1]), float(col_cosine[2]),
    ]

    slice_files = []
    for z in range(n_slices):
        sop_uid = generate_uid()
        position = affine @ np.array([0, 0, z, 1])
        image_position = [float(position[0]), float(position[1]), float(position[2])]

        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.MediaStorageSOPClassUID = MRImageStorage
        ds.file_meta.MediaStorageSOPInstanceUID = sop_uid
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

        ds.SOPClassUID = MRImageStorage
        ds.SOPInstanceUID = sop_uid
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid

        ds.PatientName = patient_name
        ds.PatientID = patient_id
        ds.StudyDescription = study_desc
        ds.SeriesDescription = "T1w MPRAGE"
        ds.Manufacturer = "OpenNeuro"
        ds.Modality = "MR"
        ds.MagneticFieldStrength = "3"

        ds.InstanceNumber = z + 1
        ds.ImagePositionPatient = image_position
        ds.ImageOrientationPatient = image_orientation
        ds.PixelSpacing = pixel_spacing
        ds.SliceThickness = slice_thickness
        ds.SpacingBetweenSlices = slice_thickness

        ds.Rows = rows
        ds.Columns = cols
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.RescaleSlope = f"{slope:.6f}"
        ds.RescaleIntercept = "0"
        ds.RescaleType = "US"

        ds.PixelData = data_u16[:, :, z].tobytes()

        buf = BytesIO()
        ds.save_as(buf, enforce_file_format=True)
        slice_files.append(buf.getvalue())

    return study_uid, series_uid, slice_files


def upload_to_orthanc(slice_files, orthanc_url, label=None):
    """Upload DICOM slices to Orthanc via REST API."""
    study_ids = set()
    with httpx.Client(timeout=120) as client:
        for i, raw in enumerate(slice_files):
            r = client.post(f"{orthanc_url}/instances", content=raw)
            if r.status_code not in (200, 201):
                print(f"  WARN: slice {i} HTTP {r.status_code}")
                continue
            resp = r.json()
            study_ids.add(resp.get("ParentStudy", ""))

    if label:
        with httpx.Client(timeout=30) as client:
            for sid in study_ids:
                client.put(f"{orthanc_url}/studies/{sid}/labels/{label}")

    return {"studies": list(study_ids), "instances": len(slice_files)}


def main():
    parser = argparse.ArgumentParser(description="NIfTI T1w -> DICOM -> Orthanc")
    parser.add_argument("bids_dir", help="BIDS dataset directory")
    parser.add_argument("--limit", type=int, default=0, help="Max subjects (0=all)")
    parser.add_argument("--orthanc", default="http://localhost:8042")
    parser.add_argument("--label", default=None, help="Orthanc label (public/private)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bids_dir = os.path.abspath(args.bids_dir)
    participants = load_participants(bids_dir)

    t1w_files = sorted(glob.glob(os.path.join(bids_dir, "sub-*", "anat", "*_T1w.nii.gz")))
    if args.limit > 0:
        t1w_files = t1w_files[:args.limit]

    print(f"Found {len(t1w_files)} T1w files in {bids_dir}")
    print(f"Orthanc: {args.orthanc}  Label: {args.label or '(none)'}\n")

    total_instances = 0
    for i, t1w_path in enumerate(t1w_files):
        sub_id = os.path.basename(os.path.dirname(os.path.dirname(t1w_path)))
        sub_num = sub_id.replace("sub-", "")
        info = participants.get(sub_num, {})
        diag = info.get("diagnosis", "?")
        age = info.get("age", "?")
        gender = info.get("gender", "?")

        print(f"[{i+1}/{len(t1w_files)}] {sub_id} ({diag}, age={age}, sex={gender})")

        if args.dry_run:
            print(f"  DRY RUN: would convert {t1w_path}")
            continue

        try:
            study_uid, series_uid, slices = nifti_to_dicom_slices(
                t1w_path,
                patient_name=f"ds000030-{sub_num}",
                patient_id=f"ds000030-{sub_num}",
            )
            print(f"  Converted: {len(slices)} slices")
            result = upload_to_orthanc(slices, args.orthanc, label=args.label)
            print(f"  Uploaded: {result['instances']} instances, {len(result['studies'])} study")
            total_instances += result["instances"]
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone. Total instances: {total_instances}")


if __name__ == "__main__":
    main()
