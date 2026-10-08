#!/bin/sh
# Constant-rate load test of POST /extract, reproducing the professor's profile:
# 50 req/s for 30 s (1,500 requests) rotating the 4 PDFs, client timeout 30 s.
# The PDF goes as the raw request body, the other input format the TP allows.
# PDF_SET picks the documents: "profesor" (default, the TP's official set) or "sinteticos".
#
# Usage (from the repo root, with the service running):
#   docker run --rm -v "$PWD/tests/stress:/scripts" -e BASE_URL=http://host.docker.internal:8080 \
#     --entrypoint sh peterevans/vegeta /scripts/vegeta-constant.sh
set -eu

BASE_URL="${BASE_URL:-http://localhost:8080}"
RATE="${RATE:-50}"
DURATION="${DURATION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"
case "${PDF_SET:-profesor}" in
  profesor) PDF_DIR="$(dirname "$0")/pdfs" ;;
  sinteticos) PDF_DIR="$(dirname "$0")/pdfs-sinteticos" ;;
  *) echo "PDF_SET must be 'profesor' or 'sinteticos'" >&2; exit 1 ;;
esac
TARGETS="$(mktemp)"

# Vegeta cycles through the targets in order, so the PDFs are sent round robin.
for pdf in "$PDF_DIR"/*.pdf; do
  printf 'POST %s/extract\nContent-Type: application/pdf\n@%s\n\n' "$BASE_URL" "$pdf" >> "$TARGETS"
done

vegeta attack -targets="$TARGETS" -rate="$RATE" -duration="$DURATION" -timeout="$TIMEOUT" | vegeta report
