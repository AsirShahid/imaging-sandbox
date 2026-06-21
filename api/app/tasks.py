"""CPU-bound jobs executed by the RQ worker (never inline in a request)."""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image
from skimage.data import shepp_logan_phantom
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from skimage.transform import iradon, radon, resize


def _png_b64(arr: np.ndarray) -> str:
    a = arr.astype(np.float64)
    lo, hi = float(a.min()), float(a.max())
    a = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    buf = io.BytesIO()
    Image.fromarray((a * 255).astype(np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def reconstruct_phantom(
    n_angles: int = 180,
    filter_name: str = "ramp",
    size: int = 256,
) -> dict:
    """Filtered-backprojection demo on a Shepp-Logan phantom.

    Returns base64 PNGs (phantom / sinogram / reconstruction) plus full-reference
    quality metrics, so you can show how angle count and filter choice trade off
    against SSIM/PSNR.
    """
    size = max(64, min(size, 512))
    n_angles = max(8, min(n_angles, 720))
    phantom = resize(shepp_logan_phantom(), (size, size), anti_aliasing=True)
    theta = np.linspace(0.0, 180.0, n_angles, endpoint=False)
    sinogram = radon(phantom, theta=theta)
    recon = np.clip(iradon(sinogram, theta=theta, filter_name=filter_name), 0.0, 1.0)
    return {
        "params": {"n_angles": n_angles, "filter": filter_name, "size": size},
        "ssim": float(structural_similarity(phantom, recon, data_range=1.0)),
        "psnr": float(peak_signal_noise_ratio(phantom, recon, data_range=1.0)),
        "phantom_png": _png_b64(phantom),
        "sinogram_png": _png_b64(sinogram),
        "reconstruction_png": _png_b64(recon),
    }
