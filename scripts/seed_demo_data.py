"""Seed Orthanc with small, redistributable public DICOM from pydicom's test data.

Run inside the api container (it has pydicom + httpx + egress):
    docker compose exec -T api python - < scripts/seed_demo_data.py

CT_small/MR_small ship inside the pydicom wheel (no download); the rest are
fetched from the pydicom-data repo and skipped gracefully if unavailable.
"""
import os

import httpx
from pydicom.data import get_testdata_file

ORTHANC = os.environ.get("ORTHANC_URL", "http://orthanc:8042")

# A varied demo set: CT, MR, a multiframe MR (scrollable), an ultrasound (which
# trips the de-id pixel-PHI warning), and an RT structure set.
NAMES = [
    "CT_small.dcm",
    "MR_small.dcm",
    "emri_small.dcm",   # multiframe MR — scroll demo
    "US1_J2KR.dcm",     # ultrasound — exercises /api/deid/check pixel-PHI flag
    "rtss.dcm",         # RT structure set
]

loaded = 0
for name in NAMES:
    try:
        path = get_testdata_file(name)
    except Exception as exc:  # noqa: BLE001 - best-effort seeding
        print(f"skip {name}: {exc}")
        continue
    if not path or not os.path.exists(path):
        print(f"skip {name}: not available")
        continue
    with open(path, "rb") as fh:
        data = fh.read()
    r = httpx.post(f"{ORTHANC}/instances", content=data, timeout=60)
    if r.status_code in (200, 201):
        print(f"loaded {name} ({len(data):,} bytes)")
        loaded += 1
    else:
        print(f"FAILED {name}: HTTP {r.status_code} {r.text[:200]}")

print(f"\nDone: {loaded} instance(s) loaded.")
stats = httpx.get(f"{ORTHANC}/statistics", timeout=30).json()
print("Orthanc now holds:", {k: stats[k] for k in
      ("CountPatients", "CountStudies", "CountSeries", "CountInstances") if k in stats})
