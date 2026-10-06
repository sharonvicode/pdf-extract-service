#!/bin/sh
# Constant-rate load test of POST /extract, reproducing the professor's profile:
# 50 req/s for 30 s (1,500 requests) rotating the 4 PDFs, client timeout 30 s.
# The PDF goes as the raw request body, the other input format the TP allows.
#
# Usage (from the repo root, with the service running):
#   docker run --rm -v "$PWD/tests/stress:/scripts" -e BASE_URL=http://host.docker.internal:8000 \
#     --entrypoint sh peterevans/vegeta /scripts/vegeta-constant.sh
set -eu

BASE_URL="${BASE_URL:-http://localhost:8000}"
RATE="${RATE:-50}"
DURATION="${DURATION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"
PDF_DIR="$(dirname "$0")/pdfs"
TARGETS="$(mktemp)"

# Vegeta cycles through the targets in order, so the 4 PDFs are sent round robin.
for pdf in liviano mediano largo pesado; do
  printf 'POST %s/extract\nContent-Type: application/pdf\n@%s/%s.pdf\n\n' "$BASE_URL" "$PDF_DIR" "$pdf" >> "$TARGETS"
done

vegeta attack -targets="$TARGETS" -rate="$RATE" -duration="$DURATION" -timeout="$TIMEOUT" | vegeta report
