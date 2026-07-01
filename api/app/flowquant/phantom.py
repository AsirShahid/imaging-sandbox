"""Digital phase-contrast MRI flow phantom (ground-truth generator).

Synthesizes a cardiac-gated PC acquisition from a *prescribed* flow waveform, so
the quantifier's output can be compared against a known truth. A circular ROI
("cerebral aqueduct") carries a parabolic velocity profile scaled, frame by frame,
so the spatial flow integral equals the target waveform Q_true(t). The velocity is
encoded to phase at a chosen VENC (modelling aliasing), and complex Gaussian noise
is added at a target SNR.

This is the validation analogue of the AMS-325 FBP work: build a known ground truth,
recover the quantity of interest, and measure the error.
"""
from __future__ import annotations

import numpy as np

from .quantify import flow_metrics, velocity_to_phase


def csf_waveform(n_frames: int) -> np.ndarray:
    """Normalized biphasic aqueductal CSF waveform (systolic down / diastolic up).

    Returns a unit-amplitude shape (mm^3/s per unit) over one cardiac cycle; the
    caller scales it to hit a target stroke volume.
    """
    t = np.linspace(0.0, 2.0 * np.pi, n_frames, endpoint=False)
    # Fundamental plus a touch of second harmonic for a sharper systolic peak.
    w = np.sin(t) + 0.3 * np.sin(2.0 * t)
    return w / np.max(np.abs(w))


def make_pc_phantom(
    n_frames: int = 20,
    heart_rate_bpm: float = 60.0,
    fov_mm: float = 64.0,
    matrix: int = 128,
    roi_radius_mm: float = 1.5,
    venc_cm_s: float = 8.0,
    snr: float = 30.0,
    stroke_volume_uL: float = 40.0,
    seed: int = 0,
) -> dict:
    """Build a PC-MRI phantom with a known aqueductal stroke volume.

    Returns magnitude/phase stacks plus the ground-truth mask, waveform, and
    metrics, and the acquisition parameters needed to quantify it.
    """
    if n_frames < 2:
        raise ValueError("n_frames must be >= 2 for a meaningful waveform")
    rng = np.random.default_rng(seed)
    dt = 60.0 / heart_rate_bpm / n_frames
    pixel = fov_mm / matrix
    pixel_area = pixel * pixel

    # Scale the normalized waveform to the requested stroke volume.
    shape = csf_waveform(n_frames)
    sv_unit = flow_metrics(shape, dt)["stroke_volume_uL"]
    q_true = shape * (stroke_volume_uL / sv_unit)  # mm^3/s == uL/s

    # Spatial geometry: circular ROI with a parabolic (Poiseuille) profile.
    coords = (np.arange(matrix) - matrix / 2.0 + 0.5) * pixel
    xx, yy = np.meshgrid(coords, coords)
    radius = np.hypot(xx, yy)
    disc = radius <= roi_radius_mm
    profile = np.clip(1.0 - (radius / roi_radius_mm) ** 2, 0.0, None) * disc
    sum_profile = float(profile.sum())

    # Per-frame velocity (cm/s) so that ROI flow integrates to q_true exactly:
    #   sum(v)*10*pixel_area = q_true  ->  v = s * profile, s = q_true / (10*A*sum)
    velocity = np.empty((n_frames, matrix, matrix))
    for i in range(n_frames):
        s = q_true[i] / (10.0 * pixel_area * sum_profile)
        velocity[i] = s * profile

    # Magnitude: vessel brighter than static background (constant over the cycle).
    magnitude = np.repeat((0.3 + 0.7 * disc)[None], n_frames, axis=0)

    # Encode to wrapped phase, add complex Gaussian noise at the target SNR.
    signal = magnitude * np.exp(1j * velocity_to_phase(velocity, venc_cm_s))
    sigma = magnitude.max() / snr if snr > 0 else 0.0
    if sigma > 0:
        signal = signal + rng.normal(0.0, sigma, signal.shape) + 1j * rng.normal(
            0.0, sigma, signal.shape
        )

    peak_velocity = float(np.abs(velocity[:, disc]).max())
    return {
        "magnitude": np.abs(signal),
        "phase": np.angle(signal),
        "velocity_true_cm_s": velocity,
        "pixel_spacing_mm": (pixel, pixel),
        "dt": dt,
        "time_s": np.arange(n_frames) * dt,
        "true_mask": disc,
        "Q_true_uL_s": q_true,
        "true_metrics": flow_metrics(q_true, dt, peak_velocity_cm_s=peak_velocity),
        "venc_cm_s": venc_cm_s,
        "params": {
            "n_frames": n_frames,
            "heart_rate_bpm": heart_rate_bpm,
            "fov_mm": fov_mm,
            "matrix": matrix,
            "roi_radius_mm": roi_radius_mm,
            "venc_cm_s": venc_cm_s,
            "snr": snr,
            "stroke_volume_uL": stroke_volume_uL,
            "seed": seed,
        },
    }
