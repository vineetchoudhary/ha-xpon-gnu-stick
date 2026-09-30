#!/usr/bin/env bash
# Run the local simulator suite; access the physical ONU only with --live.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

usage() {
    cat <<'EOF'
Usage: ./scripts/test.sh [--setup] [--live --host URL [--username USER]]

  --setup          Create .venv if needed and install requirements-dev.txt.
                   Uses Python 3.14 (override the executable with PYTHON).
  --live           Also read the real ONU's Device Status and PON Status pages.
  --host URL       Your ONU management address (required with --live).
  --username USER  Prompt privately for the ONU password during --live.
  -h, --help       Show this help.

Without --live, tests use captured HTML and a localhost simulator.
Complete output is saved in .test-results/. No ONU settings are changed.
EOF
}

setup=0
live=0
host=""
username=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup) setup=1; shift ;;
        --live) live=1; shift ;;
        --host|--username)
            if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
                printf 'Missing value for %s\n' "$1" >&2
                exit 2
            fi
            if [[ "$1" == --host ]]; then host="$2"; else username="$2"; fi
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ "$live" -eq 0 && ( -n "$host" || -n "$username" ) ]]; then
    printf '%s\n' '--host and --username require --live.' >&2
    exit 2
fi
if [[ "$live" -eq 1 && -z "$host" ]]; then
    printf '%s\n' '--live requires --host with your ONU management address.' >&2
    exit 2
fi

mkdir -p .test-results
LOG_FILE="$REPO_ROOT/.test-results/test-$(date +%Y%m%d-%H%M%S)-$$.log"
trap 'result=$?; { if [[ "$result" -ne 0 ]]; then printf "Checks failed (exit %s).\n" "$result"; fi; printf "Log: %s\n" "$LOG_FILE"; } | tee -a "$LOG_FILE"' EXIT

run() {
    "$@" 2>&1 | tee -a "$LOG_FILE"
}

TEST_PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$TEST_PYTHON" ]]; then
    if [[ "$setup" -eq 0 ]]; then
        printf '%s\n' 'Test environment missing. Run ./scripts/test.sh --setup first.' | tee -a "$LOG_FILE" >&2
        exit 1
    fi
    bootstrap_python="${PYTHON:-python3.14}"
    if ! command -v "$bootstrap_python" >/dev/null 2>&1; then
        printf 'Python 3.14 is required. Install it or set PYTHON to its executable.\n' | tee -a "$LOG_FILE" >&2
        exit 1
    fi
    run "$bootstrap_python" -m venv .venv
fi

run "$TEST_PYTHON" -c 'import sys; print("Python", sys.version.split()[0]); sys.exit(0 if (3, 14, 2) <= sys.version_info < (3, 15) else "Use Python 3.14.2 or newer in the 3.14 series for the pinned Home Assistant tests.")'
if [[ "$setup" -eq 1 ]]; then
    run "$TEST_PYTHON" -m pip install -r requirements-dev.txt
fi

run bash -n scripts/test.sh
run "$TEST_PYTHON" tools/validate_repository.py
run "$TEST_PYTHON" -m pip check
run "$TEST_PYTHON" -m ruff check custom_components tests tools
run "$TEST_PYTHON" -m ruff format --check custom_components tests tools
run "$TEST_PYTHON" -m pytest -q --tb=short

if [[ "$live" -eq 1 ]]; then
    live_args=(--host "$host")
    if [[ -n "$username" ]]; then live_args+=(--username "$username"); fi
    # The password is read by getpass, never passed as an argument.
    run "$TEST_PYTHON" tools/check_status.py "${live_args[@]}"
fi

printf '%s\n' 'All requested checks passed.' | tee -a "$LOG_FILE"
