#!/usr/bin/env bash
# Admin-only: load curated public DICOM into Orthanc.
# Runs against the loopback admin port (127.0.0.1:8042) — open an SSH tunnel
# first if you're on your laptop:   ssh -L 8042:localhost:8042 you@your-vps
#
# Usage: ./load_sample_data.sh <dir-with-dcm-files>
set -euo pipefail

ORTHANC="${ORTHANC:-http://localhost:8042}"
DIR="${1:?usage: load_sample_data.sh <dir-with-dcm>}"

count=0
while IFS= read -r -d '' f; do
  echo "Uploading: $f"
  curl -fsS -X POST "$ORTHANC/instances" --data-binary @"$f" -H 'Expect:' > /dev/null
  count=$((count + 1))
done < <(find "$DIR" -type f \( -iname '*.dcm' -o -iname '*.dicom' \) -print0)

echo "Done. Uploaded $count instance(s)."
