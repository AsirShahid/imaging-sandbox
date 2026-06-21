# Offline pipeline (workstation only)

Heavy ML (torch/MONAI) **does not run on the VPS** — a ~2GB box can't host it
alongside Orthanc + Postgres + OHIF. Instead you run inference locally, turn the
result into a standards-compliant **DICOM SEG**, and push it to Orthanc so it
overlays on the source study in OHIF.

```
local: CT series ──MONAI──► mask ──highdicom──► DICOM SEG ──STOW──► Orthanc ──► OHIF overlay
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # or GPU build
pip install -r requirements-offline.txt
```

## Run

```bash
# 1. write a SEG locally from a DICOM series folder
python segment_to_seg.py /path/to/series --out seg.dcm

# 2. push it to the VPS Orthanc through an SSH tunnel
ssh -L 8042:localhost:8042 you@your-vps        # leave open in another shell
python segment_to_seg.py /path/to/series --out seg.dcm \
    --stow http://localhost:8042/dicom-web
```

`segment()` ships with a trivial threshold so it runs with zero weights — swap in
a MONAI bundle where marked. The coded concepts in `build_seg()` are placeholders;
pick real SNOMED codes for what you segment.
