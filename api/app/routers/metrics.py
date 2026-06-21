from __future__ import annotations

import io

import numpy as np
import pydicom
from fastapi import APIRouter, HTTPException, Query
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from skimage.restoration import estimate_sigma

from ..orthanc_client import find_instances, get_instance_file

router = APIRouter(prefix="/metrics", tags=["image-quality"])


def _pixels(sop_uid: str) -> np.ndarray:
    ids = find_instances(sop_uid=sop_uid, limit=1)
    if not ids:
        raise HTTPException(404, f"No instance for SOPInstanceUID {sop_uid}")
    ds = pydicom.dcmread(io.BytesIO(get_instance_file(ids[0])))
    arr = ds.pixel_array
    if arr.ndim != 2:
        raise HTTPException(400, f"Expected a single 2D frame, got shape {arr.shape}")
    return arr.astype(np.float64)


def _normalize(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


@router.get("/single")
def single_image_quality(sop_uid: str = Query(..., description="SOPInstanceUID")) -> dict:
    """No-reference metrics for one image: estimated noise sigma and RMS contrast."""
    img = _pixels(sop_uid)
    norm = _normalize(img)
    return {
        "shape": list(img.shape),
        "noise_sigma": float(np.mean(estimate_sigma(norm))),
        "rms_contrast": float(norm.std()),
        "mean": float(img.mean()),
        "min": float(img.min()),
        "max": float(img.max()),
    }


@router.get("/compare")
def compare(
    reference_sop_uid: str = Query(..., description="Ground-truth image"),
    test_sop_uid: str = Query(..., description="Degraded/reconstructed image"),
) -> dict:
    """Full-reference metrics (SSIM, PSNR) between two same-size images."""
    ref = _normalize(_pixels(reference_sop_uid))
    test = _normalize(_pixels(test_sop_uid))
    if ref.shape != test.shape:
        raise HTTPException(400, f"Shape mismatch {ref.shape} vs {test.shape}")
    return {
        "ssim": float(structural_similarity(ref, test, data_range=1.0)),
        "psnr": float(peak_signal_noise_ratio(ref, test, data_range=1.0)),
        "shape": list(ref.shape),
    }
