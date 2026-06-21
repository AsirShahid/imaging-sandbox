#!/usr/bin/env bash
# Back up the Orthanc index (Postgres) and the DICOM storage volume.
# Run from the repo root on the VPS.
#
# Usage: ./scripts/backup.sh [output-dir]
set -euo pipefail

OUT="${1:-./backups}"
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

echo "Dumping Postgres index..."
docker compose exec -T postgres pg_dump -U orthanc orthanc | gzip > "$OUT/orthanc-db-$TS.sql.gz"

echo "Archiving Orthanc storage volume..."
docker run --rm \
  -v imaging-sandbox_orthanc_storage:/data:ro \
  -v "$(pwd)/$OUT":/backup \
  alpine tar czf "/backup/orthanc-storage-$TS.tar.gz" -C /data .

echo "Backup written to $OUT/"
