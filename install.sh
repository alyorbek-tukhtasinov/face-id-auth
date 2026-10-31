#!/usr/bin/env bash
# FaceID Next — Linux/macOS uchun o'rnatish
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for v in python3.13 python3.12 python3.11 python3; do
    if command -v "$v" >/dev/null && "$v" -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then PY="$v"; break; fi
  done
fi
[ -n "$PY" ] || { echo "Python 3.11+ topilmadi"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m faceid models
python -m faceid doctor
echo "Tayyor! Ishga tushirish: ./run.sh"
