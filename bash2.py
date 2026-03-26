#!/usr/bin/env bash
# scnd_try
# Ready-to-run helper to create venv, install requirements and run faculty_profile_extractor.py
# Usage:
#   ./scnd_try [--render] [input_urls.txt] [results.jsonl] [./pages]
# Examples:
#   ./scnd_try
#   ./scnd_try urls.txt results.jsonl ./pages
#   ./scnd_try --render urls.txt results.jsonl ./pages

set -euo pipefail
IFS=$'\n\t'

SCRIPT_NAME="$(basename "$0")"
VENV_DIR=".venv_scnd_try"
PY_SCRIPT="faculty_profile_extractor.py"

usage() {
  cat <<EOF
$SCRIPT_NAME - quick runner for faculty_profile_extractor.py

Usage:
  $SCRIPT_NAME [--render] [input_urls] [output_jsonl] [savedir]

Defaults:
  input_urls = urls.txt
  output_jsonl = results.jsonl
  savedir = ./pages

Options:
  --render    Use Selenium rendering (requires ChromeDriver + selenium in venv)

Examples:
  $SCRIPT_NAME
  $SCRIPT_NAME --render urls.txt results.jsonl ./pages
EOF
}

if [[ ${1-} == "-h" || ${1-} == "--help" ]]; then
  usage
  exit 0
fi

RENDER=false
if [[ ${1-} == "--render" ]]; then
  RENDER=true
  shift || true
fi

INPUT=${1-"urls.txt"}
OUTPUT=${2-"results.jsonl"}
SAVEDIR=${3-"./pages"}

# Basic checks
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed or not on PATH. Install Python 3.8+ and retry." >&2
  exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
  echo "ERROR: $PY_SCRIPT not found in the current directory. Please place faculty_profile_extractor.py here." >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "WARNING: input file '$INPUT' not found. Creating an empty '$INPUT'. Add one URL per line and re-run." >&2
  touch "$INPUT"
fi

mkdir -p "$SAVEDIR"

# Create venv if missing
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment in $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Upgrade pip and install requirements
python -m pip install --upgrade pip setuptools wheel
python -m pip install requests beautifulsoup4 lxml tqdm || true

if $RENDER; then
  echo "--render requested: installing selenium (in venv)"
  python -m pip install selenium || true
  # quick chromedriver check
  if ! command -v chromedriver >/dev/null 2>&1 && ! command -v chromedriver.exe >/dev/null 2>&1; then
    echo "WARNING: chromedriver not found on PATH. If you intend to use --render, install ChromeDriver matching your Chrome version and ensure 'chromedriver' is on PATH." >&2
    echo "See: https://chromedriver.chromium.org/downloads"
  fi
fi

# Run the extractor
CMD=("python" "$PY_SCRIPT" "--input" "$INPUT" "--output" "$OUTPUT" "--savedir" "$SAVEDIR")
if $RENDER; then
  CMD+=("--render")
fi

echo "Running: ${CMD[*]}"
"${CMD[@]}"

# Summary
if [[ -f "$OUTPUT" ]]; then
  COUNT=$(wc -l < "$OUTPUT" || echo 0)
  echo "\nDone. Output file: $OUTPUT (approx $COUNT lines/records)"
  echo "Showing up to first 3 lines of $OUTPUT:\n"
  head -n 3 "$OUTPUT" || true
else
  echo "No output file produced. Check logs above for errors." >&2
fi

# Deactivate venv
deactivate 2>/dev/null || true

exit 0
