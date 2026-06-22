"""Tests for the PC-MRI flow quantifier, the phantom, and the public queue guard."""
import numpy as np
import pytest
from fastapi import HTTPException

from app.flowquant import validate
from app.flowquant.phantom import make_pc_phantom
from app.flowquant.quantify import (
    flow_metrics,
    phase_to_velocity,
    quantify,
    velocity_to_phase,
)


def test_phase_velocity_roundtrip_within_venc():
    """Below VENC, encode/decode is exact (no wrap)."""
    venc = 10.0
    v = np.linspace(-9.0, 9.0, 50)  # all |v| < venc
    assert np.allclose(phase_to_velocity(velocity_to_phase(v, venc), venc), v)


def test_velocity_above_venc_aliases():
    """Above VENC the recovered velocity wraps (aliases) — motivates anti-alias."""
    venc = 5.0
    v = 7.0  # > venc
    recovered = phase_to_velocity(velocity_to_phase(v, venc), venc)
    assert not np.isclose(recovered, v)


def test_flow_metrics_on_symmetric_waveform():
    """A pure sine flow: equal forward/reverse, ~zero net, SV == forward volume."""
    n, dt = 360, 0.01
    q = 3.0 * np.sin(np.linspace(0, 2 * np.pi, n, endpoint=False))
    m = flow_metrics(q, dt)
    assert m["net_volume_uL"] == pytest.approx(0.0, abs=1e-9)
    assert m["forward_volume_uL"] == pytest.approx(m["reverse_volume_uL"], rel=1e-6)
    assert m["stroke_volume_uL"] == pytest.approx(m["forward_volume_uL"], rel=1e-6)


def test_phantom_quantify_exact_without_noise_or_aliasing():
    """Ground-truth recovery: perfect ROI, no noise, VENC above peak velocity."""
    ph = make_pc_phantom(venc_cm_s=50.0, snr=0.0, stroke_volume_uL=40.0)
    assert ph["true_metrics"]["peak_velocity_cm_s"] < 50.0  # guard: no aliasing
    res = quantify(
        ph["magnitude"], ph["phase"], ph["venc_cm_s"],
        ph["pixel_spacing_mm"], ph["dt"], mask=ph["true_mask"],
    )
    sv_t = ph["true_metrics"]["stroke_volume_uL"]
    assert res["metrics"]["stroke_volume_uL"] == pytest.approx(sv_t, rel=1e-6)
    assert res["metrics"]["net_volume_uL"] == pytest.approx(0.0, abs=1e-6)


def test_prescribed_stroke_volume_is_honored():
    ph = make_pc_phantom(venc_cm_s=50.0, snr=0.0, stroke_volume_uL=63.0)
    assert ph["true_metrics"]["stroke_volume_uL"] == pytest.approx(63.0, rel=1e-6)


def test_anti_alias_recovers_peak_velocity_under_mild_aliasing():
    """With VENC just below peak velocity, temporal unwrap recovers the true peak."""
    ref = make_pc_phantom(venc_cm_s=1000.0, snr=0.0)
    vmax = ref["true_metrics"]["peak_velocity_cm_s"]
    ph = make_pc_phantom(venc_cm_s=0.85 * vmax, snr=0.0)  # mild aliasing

    common = dict(
        magnitude_stack=ph["magnitude"], phase_stack=ph["phase"],
        venc=ph["venc_cm_s"], pixel_spacing_mm=ph["pixel_spacing_mm"],
        dt=ph["dt"], mask=ph["true_mask"],
    )
    peak_aliased = quantify(**common, anti_alias=False)["metrics"]["peak_velocity_cm_s"]
    peak_fixed = quantify(**common, anti_alias=True)["metrics"]["peak_velocity_cm_s"]

    assert peak_aliased < 0.9 * vmax  # aliasing suppressed the peak
    assert abs(peak_fixed - vmax) < abs(peak_aliased - vmax)  # unwrap helps


def test_snr_sweep_error_decreases_with_more_signal():
    """Validation harness: higher SNR -> lower stroke-volume error (monotone-ish)."""
    sweep = validate.sweep_snr([5, 40], n_seeds=6, venc_cm_s=50.0)
    assert sweep["mean_rel_error"][0] > sweep["mean_rel_error"][-1]


def test_enqueue_capped_rejects_full_queue(monkeypatch):
    """Public backlog guard returns HTTP 429 when the queue is saturated."""
    from app import queue as q

    class _FullQueue:
        def __len__(self):
            return q.MAX_PENDING_JOBS

    monkeypatch.setattr(q, "get_queue", lambda: _FullQueue())
    with pytest.raises(HTTPException) as exc:
        q.enqueue_capped("app.tasks.reconstruct_phantom", 180, "ramp", 256)
    assert exc.value.status_code == 429
