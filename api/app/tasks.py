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


def quantify_pc_flow(
    venc_cm_s: float = 8.0,
    snr: float = 30.0,
    stroke_volume_uL: float = 40.0,
    heart_rate_bpm: float = 60.0,
    anti_alias: bool = False,
    seed: int = 0,
) -> dict:
    """Phase-contrast CSF-flow demo: synthesize a ground-truth phantom, quantify it,
    and report recovered-vs-true flow metrics with diagnostic plots.

    Mirrors the lab's PC-MRI analysis (aqueductal CSF stroke volume, an iNPH
    biomarker) while keeping the truth known, so accuracy is measurable.
    """
    from .flowquant import plots
    from .flowquant.phantom import make_pc_phantom
    from .flowquant.quantify import quantify

    ph = make_pc_phantom(
        venc_cm_s=venc_cm_s,
        snr=snr,
        stroke_volume_uL=stroke_volume_uL,
        heart_rate_bpm=heart_rate_bpm,
        seed=seed,
    )
    res = quantify(
        ph["magnitude"],
        ph["phase"],
        venc_cm_s,
        ph["pixel_spacing_mm"],
        ph["dt"],
        mask=ph["true_mask"],
        anti_alias=anti_alias,
    )

    true_m, rec_m = ph["true_metrics"], res["metrics"]
    sv_t = true_m["stroke_volume_uL"]
    peak_frame = int(np.argmax(np.abs(ph["Q_true_uL_s"])))
    return {
        "params": {**ph["params"], "anti_alias": anti_alias},
        "true": true_m,
        "recovered": rec_m,
        "stroke_volume_rel_error": abs(rec_m["stroke_volume_uL"] - sv_t) / sv_t,
        "flow_curve_png": plots.flow_curve_png(
            ph["time_s"], res["flow_uL_s"], flow_true=ph["Q_true_uL_s"]
        ),
        "velocity_overlay_png": plots.velocity_overlay_png(
            ph["magnitude"][peak_frame],
            res["velocity_cm_s"][peak_frame],
            res["mask"],
        ),
    }


def quantify_pc_validate(n_seeds: int = 10) -> dict:
    """Validation sweeps: stroke-volume error vs SNR and vs VENC (mean +/- SEM)."""
    from .flowquant import plots, validate
    from .flowquant.phantom import make_pc_phantom

    snr_sweep = validate.sweep_snr([5, 10, 20, 40, 80], n_seeds=n_seeds)

    # Probe VENC relative to the phantom's peak velocity so the aliasing knee shows.
    vmax = make_pc_phantom(venc_cm_s=1000.0, snr=0.0)["true_metrics"][
        "peak_velocity_cm_s"
    ]
    venc_values = [round(vmax * f, 2) for f in (2.0, 1.2, 1.0, 0.8, 0.6)]
    venc_sweep = validate.sweep_venc(venc_values, n_seeds=n_seeds)

    return {
        "n_seeds": n_seeds,
        "peak_velocity_cm_s": vmax,
        "snr_sweep": snr_sweep,
        "venc_sweep": venc_sweep,
        "snr_curve_png": plots.validation_curve_png(
            snr_sweep, "Stroke-volume error vs SNR"
        ),
        "venc_curve_png": plots.validation_curve_png(
            venc_sweep, "Stroke-volume error vs VENC"
        ),
    }
