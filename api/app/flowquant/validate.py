"""Validation sweeps for the PC-MRI flow quantifier.

Mirrors the AMS-325 methodology: vary one acquisition parameter, recover the
quantity of interest over several random seeds, and report the recovered-vs-true
stroke-volume error as mean +/- SEM (reproducible, seed-controlled).
"""
from __future__ import annotations

import numpy as np

from .phantom import make_pc_phantom
from .quantify import quantify


def _sv_rel_error(seed: int, anti_alias: bool = False, **phantom_kwargs) -> float:
    """Relative stroke-volume error for one phantom realization (perfect ROI)."""
    ph = make_pc_phantom(seed=seed, **phantom_kwargs)
    res = quantify(
        ph["magnitude"],
        ph["phase"],
        ph["venc_cm_s"],
        ph["pixel_spacing_mm"],
        ph["dt"],
        mask=ph["true_mask"],
        anti_alias=anti_alias,
    )
    sv_true = ph["true_metrics"]["stroke_volume_uL"]
    sv_rec = res["metrics"]["stroke_volume_uL"]
    return abs(sv_rec - sv_true) / sv_true


def _stats(errors: list[float]) -> tuple[float, float]:
    arr = np.asarray(errors, float)
    return float(arr.mean()), float(arr.std() / np.sqrt(len(arr)))


def sweep_snr(
    snr_values: list[float], n_seeds: int = 10, venc_cm_s: float = 8.0, **kw
) -> dict:
    """Stroke-volume error vs SNR (should fall monotonically as SNR rises)."""
    mean, sem = [], []
    for snr in snr_values:
        m, s = _stats(
            [
                _sv_rel_error(seed, snr=snr, venc_cm_s=venc_cm_s, **kw)
                for seed in range(n_seeds)
            ]
        )
        mean.append(m)
        sem.append(s)
    return {"x": list(snr_values), "mean_rel_error": mean, "sem": sem,
            "xlabel": "SNR"}


def sweep_venc(
    venc_values: list[float],
    n_seeds: int = 10,
    snr: float = 60.0,
    anti_alias: bool = False,
    **kw,
) -> dict:
    """Stroke-volume error vs VENC (error rises once VENC drops below peak velocity)."""
    mean, sem = [], []
    for venc in venc_values:
        m, s = _stats(
            [
                _sv_rel_error(
                    seed, snr=snr, venc_cm_s=venc, anti_alias=anti_alias, **kw
                )
                for seed in range(n_seeds)
            ]
        )
        mean.append(m)
        sem.append(s)
    return {"x": list(venc_values), "mean_rel_error": mean, "sem": sem,
            "xlabel": "VENC (cm/s)"}
