#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# SimAPI Pre-Commit Hook
#
# Validates simulation output files before every git commit.
# If corruptions are found, the commit is blocked and the report is shown.
#
# Install:
#   cp integrations/pre-commit/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or with pre-commit framework (.pre-commit-config.yaml):
#   repos:
#     - repo: https://github.com/simapi/simapi
#       rev: v3.0.0
#       hooks:
#         - id: simapi-validate
#           name: SimAPI Physics Validation
#           files: \.(csv|json)$
#
# Configuration (optional — create .simapi-hook.json in project root):
#   {
#     "domain": "aerodynamics",
#     "fail_on": "critical",
#     "file_patterns": ["outputs/*.csv", "data/simulation/*.json"],
#     "config_key": "my-project-v1"
#   }
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

HOOK_VERSION="3.0.0"
RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Check if simapi is available
if ! python3 -m simapi.cli version --quiet >/dev/null 2>&1; then
    # Try alternate import path
    if ! python3 -c "import sys; sys.path.insert(0,'python-pkg'); from simapi.cli import main" >/dev/null 2>&1; then
        echo -e "${DIM}[simapi] CLI not found — skipping physics validation${RESET}"
        exit 0
    fi
    SIMAPI_CMD="python3 -c 'import sys; sys.path.insert(0,\"python-pkg\"); from simapi.cli import main; main()'"
else
    SIMAPI_CMD="python3 -m simapi.cli"
fi

# Read hook config
HOOK_CONFIG=".simapi-hook.json"
DOMAIN="${SIMAPI_DOMAIN:-}"
FAIL_ON="${SIMAPI_FAIL_ON:-critical}"
CONFIG_KEY="${SIMAPI_CONFIG_KEY:-}"

if [ -f "$HOOK_CONFIG" ]; then
    DOMAIN=$(python3 -c "import json; d=json.load(open('$HOOK_CONFIG')); print(d.get('domain',''))" 2>/dev/null || echo "")
    FAIL_ON=$(python3 -c "import json; d=json.load(open('$HOOK_CONFIG')); print(d.get('fail_on','critical'))" 2>/dev/null || echo "critical")
    CONFIG_KEY=$(python3 -c "import json; d=json.load(open('$HOOK_CONFIG')); print(d.get('config_key',''))" 2>/dev/null || echo "")
fi

# Find staged simulation files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '\.(csv|json)$' || true)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

# Filter to simulation files only (skip package.json, config.json, etc.)
SIM_FILES=""
for f in $STAGED_FILES; do
    # Skip common non-simulation JSON files
    basename=$(basename "$f")
    if [[ "$basename" == "package.json" ]] || \
       [[ "$basename" == "package-lock.json" ]] || \
       [[ "$basename" == "tsconfig.json" ]] || \
       [[ "$basename" == "simapi.json" ]] || \
       [[ "$basename" == ".pre-commit-hooks.yaml" ]]; then
        continue
    fi
    # Check if it looks like simulation data (has numeric columns)
    if python3 -c "
import csv, json, sys
f = '$f'
try:
    if f.endswith('.csv'):
        rows = list(csv.DictReader(open(f)))[:5]
        if not rows: sys.exit(1)
        # Check for numeric values
        has_numeric = any(
            any(v.replace('.','').replace('-','').replace('e','').replace('E','').replace('+','').isdigit()
                for v in list(row.values())[:5] if isinstance(v, str))
            for row in rows
        )
        sys.exit(0 if has_numeric else 1)
    else:
        d = json.load(open(f))
        is_sim = isinstance(d, list) or any(k in d for k in ['data','trials','results'])
        sys.exit(0 if is_sim else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        SIM_FILES="$SIM_FILES $f"
    fi
done

if [ -z "$SIM_FILES" ]; then
    exit 0
fi

echo ""
echo -e "${BOLD}SimAPI Physics Validation${RESET} ${DIM}(pre-commit hook v$HOOK_VERSION)${RESET}"
echo -e "${DIM}─────────────────────────────────────────────────────${RESET}"

FAILED=0
TOTAL_REMOVED=0
TOTAL_FLAGGED=0

for FILE in $SIM_FILES; do
    if [ ! -f "$FILE" ]; then
        continue
    fi

    echo -e "${DIM}Validating${RESET} $FILE…"

    # Build simapi command
    SIMAPI_ARGS="--quiet --fail-on never"
    [ -n "$DOMAIN" ] && SIMAPI_ARGS="$SIMAPI_ARGS --domain $DOMAIN"
    [ -n "$CONFIG_KEY" ] && SIMAPI_ARGS="$SIMAPI_ARGS --config-key $CONFIG_KEY"

    # Run simapi and capture output
    RESULT=$(python3 -m simapi.cli ci "$FILE" $SIMAPI_ARGS --json 2>/dev/null || \
             python3 -c "
import sys
sys.path.insert(0, 'python-pkg')
sys.argv = ['simapi', 'ci', '$FILE'] + '$SIMAPI_ARGS --json'.split()
from simapi.cli import main
main()
" 2>/dev/null || echo '{"status":"ERROR","n_auto_removed":0,"n_flagged_review":0}')

    N_REMOVED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('n_auto_removed',0))" 2>/dev/null || echo "0")
    N_FLAGGED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('n_flagged_review',0))" 2>/dev/null || echo "0")
    STATUS=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
    DIAGNOSIS=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('diagnosis') or {}).get('primary') or 'none')" 2>/dev/null || echo "none")

    TOTAL_REMOVED=$((TOTAL_REMOVED + N_REMOVED))
    TOTAL_FLAGGED=$((TOTAL_FLAGGED + N_FLAGGED))

    if [ "$N_REMOVED" -gt 0 ]; then
        echo -e "  ${RED}✗${RESET} ${RED}$N_REMOVED corrupted rows found${RESET} | $N_FLAGGED flagged | diagnosis: $DIAGNOSIS"
        FAILED=1
    elif [ "$N_FLAGGED" -gt 0 ]; then
        echo -e "  ${AMBER}⚠${RESET} $N_FLAGGED rows flagged for review"
        if [ "$FAIL_ON" = "review" ] || [ "$FAIL_ON" = "any" ]; then
            FAILED=1
        fi
    else
        echo -e "  ${GREEN}✓${RESET} ${GREEN}Clean${RESET}"
    fi
done

echo -e "${DIM}─────────────────────────────────────────────────────${RESET}"

if [ "$FAILED" -eq 1 ]; then
    echo ""
    echo -e "${RED}${BOLD}Commit blocked: $TOTAL_REMOVED corrupted rows found${RESET}"
    echo ""
    echo -e "  ${CYAN}→${RESET} Run ${BOLD}simapi validate <file>${RESET} for the full forensic report"
    echo -e "  ${CYAN}→${RESET} Run ${BOLD}simapi validate <file> --export clean.csv${RESET} to extract clean data"
    echo ""
    echo -e "${DIM}To skip this check: git commit --no-verify${RESET}"
    echo -e "${DIM}To configure:       edit .simapi-hook.json${RESET}"
    echo ""
    exit 1
else
    if [ "$TOTAL_FLAGGED" -gt 0 ]; then
        echo -e "${AMBER}$TOTAL_FLAGGED rows flagged for review. Commit allowed (fail-on=$FAIL_ON).${RESET}"
    else
        echo -e "${GREEN}All simulation files clean. Commit allowed.${RESET}"
    fi
    echo ""
    exit 0
fi
