#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src "${PYTHON:-python3}" -m sentinel_eval.cli run --suite data/eval_cases.jsonl --output reports/demo_report.json --markdown reports/demo_report.md
cat reports/demo_report.md
