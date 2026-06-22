#!/usr/bin/env bash
# Load the curated public demo set (TCIA, CC BY 3.0) into Orthanc.
#
# Run on the VPS, or from your laptop over an SSH tunnel:
#   ssh -L 8042:localhost:8042 vps        # then, in another shell:
#   ./scripts/load_tcia.sh
#
# Orthanc de-duplicates by SOPInstanceUID, so re-running is safe.
# Attribution / licensing: see docs/DATASETS.md
set -euo pipefail

ORTHANC="${ORTHANC:-http://localhost:8042}"
NBIA="https://services.cancerimagingarchive.net/nbia-api/services/v1"

# SeriesInstanceUID | human description
SERIES=(
  "1.2.826.0.1.3680043.2.1125.1.41202274843063370955090296887703130|Pancreas-CT  abdominal CT  (~181 slices)"
  "1.2.826.0.1.3680043.2.1125.1.77419915248783746629465382576486048|Pancreas-CT  abdominal CT  (~185 slices)"
  "1.3.6.1.4.1.14519.5.2.1.6279.6001.198489333332254008035861390326|LIDC-IDRI    chest CT      (~92 slices)"
  "1.3.6.1.4.1.14519.5.2.1.5168.1900.267475167888884755506702762438|Soft-tissue-Sarcoma  MR T2  (~40 slices)"
)

for entry in "${SERIES[@]}"; do
  uid="${entry%%|*}"; desc="${entry#*|}"
  echo ">> ${desc}"
  tmp="$(mktemp -d)"
  curl -fsS --max-time 300 -o "$tmp/series.zip" "$NBIA/getImage?SeriesInstanceUID=$uid"
  python3 -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$tmp/series.zip" "$tmp/ex"
  n=0
  for f in "$tmp"/ex/*; do
    # TCIA zips include a non-DICOM file or two; ignore those (HTTP 400).
    curl -fsS -X POST "$ORTHANC/instances" --data-binary @"$f" -H 'Expect:' >/dev/null 2>&1 && n=$((n+1)) || true
  done
  echo "   loaded ${n} instances"
  rm -rf "$tmp"
done

echo "Done."
