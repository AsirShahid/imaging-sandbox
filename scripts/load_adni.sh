#!/usr/bin/env bash
# Admin/LOCAL ONLY: load ADNI DICOM into Orthanc for your own experiments and
# tag every loaded study `private` so the public edge never lists or serves it.
#
#   ⚠  ADNI is NOT redistributable. The ADNI Data Use Agreement forbids sharing
#      the data with anyone who has not signed it, so ADNI must never go on the
#      public instance (imaging.asir.dev). Request access and sign the DUA at
#      https://adni.loni.usc.edu/ , then download the studies from LONI/IDA
#      yourself — there is no anonymous download API (unlike the TCIA loader).
#
# This script talks to the loopback admin port ONLY and refuses any non-loopback
# target. The `private` label is enforced by orthanc/private_guard.py + the proxy.
#
# Usage (on the VPS, or over an SSH tunnel: ssh -L 8042:localhost:8042 you@vps):
#   ./scripts/load_adni.sh /path/to/ADNI_export_dir
#
# Attribution / licensing: see docs/DATASETS.md
set -euo pipefail

ORTHANC="${ORTHANC:-http://localhost:8042}"
LABEL="private"  # hardcoded — ADNI must always be private (DUA forbids redistribution)
DIR="${1:?usage: load_adni.sh <dir-with-ADNI-dicom>}"

# Private data must never be pushed through the public edge — refuse anything
# that isn't the loopback admin port.
case "$ORTHANC" in
  http://localhost:*|http://127.0.0.1:*) : ;;
  *) echo "REFUSING: ORTHANC must be loopback (got '$ORTHANC'); ADNI is admin-tunnel only." >&2; exit 2 ;;
esac

declare -A studies=()
count=0
while IFS= read -r -d '' f; do
  resp="$(curl -fsS -X POST "$ORTHANC/instances" --data-binary @"$f" -H 'Expect:' 2>/dev/null)" \
    || { echo "skip (not DICOM?): $f" >&2; continue; }
  sid="$(printf '%s' "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ParentStudy",""))' 2>/dev/null || true)"
  [ -n "$sid" ] && studies["$sid"]=1
  count=$((count + 1))
done < <(find "$DIR" -type f \( -iname '*.dcm' -o -iname '*.dicom' -o -iname '*.ima' \) -print0)

echo "Uploaded $count instance(s) across ${#studies[@]} study(ies)."

for sid in "${!studies[@]}"; do
  curl -fsS -X PUT "$ORTHANC/studies/$sid/labels/$LABEL" -H 'Expect:' > /dev/null
  echo "labeled study $sid -> '$LABEL' (hidden from public DICOMweb)"
done

echo "Done. These studies are admin-only; the public edge cannot list or serve them."
