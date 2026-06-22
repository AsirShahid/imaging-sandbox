"""Phase-contrast MRI flow quantification (pure numpy).

Physics: in a phase-contrast acquisition the signal phase is linearly proportional
to through-plane velocity, wrapped into (-pi, pi]:

    phase = wrap( pi * v / VENC )   <=>   v = phase * VENC / pi

When |v| > VENC the phase wraps and the velocity *aliases*; an optional temporal
unwrap recovers it under the (usual, for cardiac-gated data) assumption that the
true phase changes by < pi between consecutive frames.

Units convention (kept explicit so the metrics are clinically legible):
    velocity   : cm/s   (VENC is also cm/s)
    pixel size : mm      -> pixel area mm^2
    flow Q(t)  : mm^3/s == microliter/s
    volumes    : microliter (uL)
"""
from __future__ import annotations

import numpy as np

ArrayLike = np.ndarray


def wrap_to_pi(phase: ArrayLike) -> np.ndarray:
    """Wrap radians into (-pi, pi]."""
    return (np.asarray(phase, float) + np.pi) % (2 * np.pi) - np.pi


def velocity_to_phase(velocity: ArrayLike, venc: float) -> np.ndarray:
    """Encode velocity (cm/s) as wrapped phase (radians) for a given VENC."""
    return wrap_to_pi(np.pi * np.asarray(velocity, float) / venc)


def phase_to_velocity(phase: ArrayLike, venc: float) -> np.ndarray:
    """Decode phase (radians) back to velocity (cm/s) for a given VENC."""
    return np.asarray(phase, float) * venc / np.pi


def segment_roi(magnitude_stack: ArrayLike, percentile: float = 80.0) -> np.ndarray:
    """Threshold the time-averaged magnitude into a vessel/aqueduct ROI mask."""
    mean_mag = np.asarray(magnitude_stack, float).mean(axis=0)
    thr = np.percentile(mean_mag, percentile)
    return mean_mag >= thr


def roi_flow_series(
    velocity_stack: ArrayLike, mask: ArrayLike, pixel_area_mm2: float
) -> np.ndarray:
    """Integrate velocity over the ROI per frame -> flow Q(t) in mm^3/s (uL/s).

    velocity in cm/s (x10 -> mm/s) times pixel area in mm^2, summed over the mask.
    """
    v = np.asarray(velocity_stack, float)
    mask = np.asarray(mask, bool)
    return (v * mask[None, :, :]).sum(axis=(1, 2)) * 10.0 * pixel_area_mm2


def flow_metrics(
    flow_uL_s: ArrayLike, dt: float, peak_velocity_cm_s: float | None = None
) -> dict:
    """Standard PC-MRI flow metrics from a flow curve Q(t) (uL/s) and frame dt (s)."""
    flow = np.asarray(flow_uL_s, float)
    forward = np.clip(flow, 0.0, None)
    reverse = np.clip(-flow, 0.0, None)
    forward_volume = float(forward.sum() * dt)
    reverse_volume = float(reverse.sum() * dt)
    net_volume = float(flow.sum() * dt)
    # Aqueductal stroke volume: mean of forward and backward volume per cycle.
    stroke_volume = 0.5 * (forward_volume + reverse_volume)
    cycle = float(len(flow) * dt)
    return {
        "stroke_volume_uL": stroke_volume,
        "forward_volume_uL": forward_volume,
        "reverse_volume_uL": reverse_volume,
        "net_volume_uL": net_volume,
        "mean_flow_uL_s": net_volume / cycle if cycle > 0 else 0.0,
        "regurgitant_fraction": reverse_volume / forward_volume
        if forward_volume > 0
        else 0.0,
        "peak_velocity_cm_s": float(peak_velocity_cm_s)
        if peak_velocity_cm_s is not None
        else None,
        "cycle_duration_s": cycle,
    }


def quantify(
    magnitude_stack: ArrayLike,
    phase_stack: ArrayLike,
    venc: float,
    pixel_spacing_mm: tuple[float, float],
    dt: float,
    mask: ArrayLike | None = None,
    anti_alias: bool = False,
) -> dict:
    """Full quantification: phase images -> velocity -> ROI flow -> metrics.

    Parameters mirror what a real acquisition provides (VENC, pixel spacing, the
    inter-frame time dt). ``mask`` may be supplied (e.g. a hand-drawn aqueduct ROI);
    otherwise it is segmented from the magnitude. ``anti_alias`` applies a temporal
    phase unwrap before decoding, recovering velocities above VENC.
    """
    magnitude = np.asarray(magnitude_stack, float)
    phase = np.asarray(phase_stack, float)
    if mask is None:
        mask = segment_roi(magnitude)
    mask = np.asarray(mask, bool)

    work_phase = np.unwrap(phase, axis=0) if anti_alias else phase
    velocity = phase_to_velocity(work_phase, venc)

    flow = roi_flow_series(velocity, mask, pixel_spacing_mm[0] * pixel_spacing_mm[1])
    peak = float(np.abs(velocity[:, mask]).max()) if mask.any() else 0.0
    metrics = flow_metrics(flow, dt, peak_velocity_cm_s=peak)
    return {
        "metrics": metrics,
        "flow_uL_s": flow,
        "velocity_cm_s": velocity,
        "mask": mask,
    }
