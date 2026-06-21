"""
Offline segmentation -> DICOM SEG -> Orthanc.

RUN THIS ON YOUR WORKSTATION, NOT THE VPS. This is where torch/MONAI live.
The VPS only stores and displays the resulting DICOM SEG (it overlays natively
in OHIF on the source study).

Pipeline:
  1. Load a DICOM series from a local folder.
  2. Produce a binary segmentation mask. The placeholder is a fixed intensity
     threshold so this runs with zero trained weights; swap in a MONAI bundle
     where marked in segment().
  3. Encode the mask as a DICOM SEG (highdicom) referencing the source series.
  4. (optional) STOW the SEG to Orthanc through an SSH tunnel.

Examples:
  python segment_to_seg.py ./series --out seg.dcm
  # tunnel first:  ssh -L 8042:localhost:8042 you@vps
  python segment_to_seg.py ./series --out seg.dcm --stow http://localhost:8042/dicom-web

NOTE: the coded concepts below are generic placeholders — choose proper SNOMED
codes for the anatomy/tissue you actually segment.
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import highdicom as hd
import numpy as np
import pydicom


def load_series(folder: Path) -> list[pydicom.Dataset]:
    files = sorted(folder.glob("*.dcm"))
    if not files:
        raise SystemExit(f"No .dcm files in {folder}")
    dsets = [pydicom.dcmread(str(f)) for f in files]
    dsets.sort(key=lambda d: int(getattr(d, "InstanceNumber", 0)))
    return dsets


def segment(volume: np.ndarray) -> np.ndarray:
    """Placeholder 'model': normalized intensity threshold -> binary mask.

    Replace with MONAI inference, e.g.:
        import torch
        from monai.bundle import download, load
        download(name="spleen_ct_segmentation", bundle_dir="./bundles")
        model = load("spleen_ct_segmentation", bundle_dir="./bundles")
        with torch.no_grad():
            logits = model(preprocess(volume))            # CPU build is fine
        return (logits.argmax(1)[0].cpu().numpy() > 0).astype(np.uint8)
    """
    v = volume.astype(np.float32)
    v = (v - v.min()) / (np.ptp(v) + 1e-6)
    return (v > 0.5).astype(np.uint8)


def build_seg(dsets: list[pydicom.Dataset], mask: np.ndarray) -> hd.seg.Segmentation:
    tissue = hd.sr.CodedConcept(value="85756007", scheme_designator="SCT", meaning="Tissue")
    desc = hd.seg.SegmentDescription(
        segment_number=1,
        segment_label="demo-region",
        segmented_property_category=tissue,
        segmented_property_type=tissue,
        algorithm_type=hd.seg.SegmentAlgorithmTypeValues.AUTOMATIC,
        algorithm_identification=hd.AlgorithmIdentificationSequence(
            name="threshold-demo",
            version="0.1",
            family=hd.sr.CodedConcept(
                value="123109", scheme_designator="DCM", meaning="Artificial Intelligence"
            ),
        ),
    )
    return hd.seg.Segmentation(
        source_images=dsets,
        pixel_array=mask,
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=[desc],
        series_instance_uid=hd.UID(),
        series_number=99,
        sop_instance_uid=hd.UID(),
        instance_number=1,
        manufacturer="imaging-sandbox",
        manufacturer_model_name="threshold-demo",
        software_versions="0.1",
        device_serial_number="0",
    )


def stow(seg: hd.seg.Segmentation, base_url: str) -> None:
    import httpx

    buf = io.BytesIO()
    seg.save_as(buf)
    boundary = "imaging-sandbox-boundary"
    body = (
        f"--{boundary}\r\nContent-Type: application/dicom\r\n\r\n".encode()
        + buf.getvalue()
        + f"\r\n--{boundary}--".encode()
    )
    headers = {
        "Content-Type": f'multipart/related; type="application/dicom"; boundary={boundary}'
    }
    r = httpx.post(f"{base_url.rstrip('/')}/studies", content=body, headers=headers, timeout=60)
    r.raise_for_status()
    print("STOW ok:", r.status_code)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("series_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("seg.dcm"))
    ap.add_argument("--stow", help="DICOMweb base URL, e.g. http://localhost:8042/dicom-web")
    args = ap.parse_args()

    dsets = load_series(args.series_dir)
    volume = np.stack([d.pixel_array for d in dsets])
    mask = segment(volume)
    seg = build_seg(dsets, mask)
    seg.save_as(str(args.out))
    print(f"Wrote {args.out}  (mask voxels: {int(mask.sum())})")
    if args.stow:
        stow(seg, args.stow)


if __name__ == "__main__":
    main()
