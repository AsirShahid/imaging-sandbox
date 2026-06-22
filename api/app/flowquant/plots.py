"""Matplotlib (Agg) renderers -> base64 PNG, for the worker task outputs.

Imported lazily by the task layer so the numeric core stays matplotlib-free.
"""
from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _fig_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def flow_curve_png(time_s, flow_recovered, flow_true=None) -> str:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.axhline(0.0, color="0.7", lw=0.8)
    if flow_true is not None:
        ax.plot(time_s, flow_true, "k--", lw=1.5, label="ground truth")
    ax.plot(time_s, flow_recovered, "C0-o", ms=3, label="recovered")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("CSF flow (µL/s)")
    ax.set_title("Aqueductal flow over the cardiac cycle")
    ax.legend(fontsize=8)
    return _fig_b64(fig)


def velocity_overlay_png(magnitude, velocity, mask) -> str:
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(magnitude, cmap="gray")
    vmax = float(np.abs(velocity).max()) or 1.0
    masked = np.ma.masked_where(~np.asarray(mask, bool), velocity)
    im = ax.imshow(masked, cmap="RdBu_r", vmin=-vmax, vmax=vmax, alpha=0.85)
    ax.contour(np.asarray(mask, float), levels=[0.5], colors="lime", linewidths=0.8)
    ax.set_axis_off()
    ax.set_title("Through-plane velocity (cm/s)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    return _fig_b64(fig)


def validation_curve_png(sweep: dict, title: str) -> str:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.errorbar(
        sweep["x"],
        np.asarray(sweep["mean_rel_error"]) * 100.0,
        yerr=np.asarray(sweep["sem"]) * 100.0,
        fmt="C0-o",
        capsize=3,
    )
    ax.set_xlabel(sweep["xlabel"])
    ax.set_ylabel("stroke-volume error (%)")
    ax.set_title(title)
    return _fig_b64(fig)
