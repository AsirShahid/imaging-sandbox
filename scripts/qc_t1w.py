#!/usr/bin/env python3
"""
T1w QC script: load a NIfTI image, print header metadata, show 3-plane slices,
and generate a QC PNG.

Usage:
    python qc_t1w.py <nifti_path> [output_png]

Example:
    python qc_t1w.py /srv/neurodata/openneuro/raw/ds000030/sub-10159/anat/sub-10159_T1w.nii.gz
"""

import sys
import os
import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timezone


def qc_t1w(nifti_path: str, output_png: str | None = None) -> dict:
    """Load a T1w NIfTI, print metadata, generate QC image, return summary dict."""
    
    if not os.path.exists(nifti_path):
        raise FileNotFoundError(f"File not found: {nifti_path}")

    img = nib.load(nifti_path)
    data = img.get_fdata()
    hdr = img.header

    # --- Header metadata ---
    info = {
        "file": os.path.basename(nifti_path),
        "shape": img.shape,
        "voxel_size_mm": [float(z) for z in hdr.get_zooms()],
        "dtype": str(hdr.get_data_dtype()),
        "affine_diag": [round(float(x), 2) for x in np.diag(img.affine)[:3]],
        "data_min": round(float(data.min()), 2),
        "data_max": round(float(data.max()), 2),
        "data_mean": round(float(data.mean()), 2),
        "data_std": round(float(data.std()), 2),
        "nonzero_voxels": int(np.count_nonzero(data)),
        "total_voxels": int(data.size),
        "file_size_mb": round(os.path.getsize(nifti_path) / 1024 / 1024, 1),
        "qc_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Print to stdout
    print("=" * 60)
    print(f"T1w QC Report: {info['file']}")
    print("=" * 60)
    for k, v in info.items():
        print(f"  {k:20s}: {v}")
    print()

    # --- Generate QC PNG ---
    if output_png is None:
        output_png = nifti_path.replace('.nii.gz', '_qc.png').replace('.nii', '_qc.png')
    
    # Compute mid-slice indices
    mid = [s // 2 for s in data.shape]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    views = [
        ("Axial (z)", data[:, :, mid[2]], dict(aspect='equal')),
        ("Coronal (y)", data[:, mid[1], :], dict(aspect='equal')),
        ("Sagittal (x)", data[mid[0], :, :], dict(aspect='equal')),
    ]
    
    # Robust display range (2nd-98th percentile of nonzero voxels)
    nonzero = data[data > 0]
    if len(nonzero) > 0:
        vmin, vmax = np.percentile(nonzero, [2, 98])
    else:
        vmin, vmax = data.min(), data.max()

    for ax, (title, slc, kwargs) in zip(axes, views):
        ax.imshow(slc.T, cmap='gray', origin='lower', vmin=vmin, vmax=vmax, **kwargs)
        ax.set_title(title, fontsize=11)
        ax.axis('off')

    fig.suptitle(
        f"{info['file']}  |  {info['shape']}  |  {info['voxel_size_mm']}mm  |  {info['file_size_mb']}MB",
        fontsize=10, y=0.98
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    info["qc_png"] = output_png
    print(f"QC image saved: {output_png}")

    return info


def qc_batch(bids_dir: str, output_dir: str, max_subjects: int = 10):
    """Run QC on a batch of T1w images from a BIDS directory."""
    os.makedirs(output_dir, exist_ok=True)
    
    t1w_files = sorted([
        os.path.join(root, f)
        for root, _, files in os.walk(bids_dir)
        for f in files
        if f.endswith('_T1w.nii.gz')
    ])[:max_subjects]

    results = []
    for t1w_path in t1w_files:
        sub_id = os.path.basename(os.path.dirname(os.path.dirname(t1w_path)))
        png_path = os.path.join(output_dir, f"{sub_id}_T1w_qc.png")
        try:
            info = qc_t1w(t1w_path, png_path)
            info["subject"] = sub_id
            results.append(info)
            print(f"  [OK] {sub_id}")
        except Exception as e:
            print(f"  [FAIL] {sub_id}: {e}")
            results.append({"subject": sub_id, "error": str(e)})

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python qc_t1w.py <nifti_path> [output_png]")
        print("       python qc_t1w.py --batch <bids_dir> <output_dir> [max_subjects]")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        bids_dir = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "/srv/neurodata/openneuro/derivatives/qc"
        max_sub = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        qc_batch(bids_dir, output_dir, max_sub)
    else:
        nifti_path = sys.argv[1]
        output_png = sys.argv[2] if len(sys.argv) > 2 else None
        qc_t1w(nifti_path, output_png)
