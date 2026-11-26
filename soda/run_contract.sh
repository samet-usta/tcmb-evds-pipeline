#!/usr/bin/env bash
# Soda exit code -> pipeline exit code eşlemesi (P4-A5-S4).
# Kural: hata durur, warn devam eder ama log'da görünür.
set -uo pipefail

CONTRACT="${1:-soda/contracts/raw/evds_landing.yml}"
DS="${2:-$(date +%F)}"
REPORT_DIR="reports/soda"
REPORT="$REPORT_DIR/evds_landing_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p "$REPORT_DIR"

/opt/soda-venv/bin/soda contract verify \
  -c "$CONTRACT" -ds soda/data_sources/warehouse.yml --set ds="$DS" -v 2>&1 | tee "$REPORT"
# tee exit code'u maskeler, o yüzden PIPESTATUS okunur
code=${PIPESTATUS[0]}

case $code in
  0) echo "SODA: PASS"; exit 0 ;;
  2) echo "SODA: WARN (pipeline devam eder)"; exit 0 ;;
  1) echo "SODA: FAIL (pipeline durur)"; exit 1 ;;
  3) echo "SODA: CONTRACT/CONFIG HATASI (pipeline durur)"; exit 1 ;;
  *) echo "SODA: bilinmeyen exit code $code (pipeline durur)"; exit 1 ;;
esac
