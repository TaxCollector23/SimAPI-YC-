#!/usr/bin/env bash
#
# SimAPI CI gate.
#
# Runs the `simapi` CLI (from the simapi-cli npm package) with --json,
# parses the verdict, writes GitHub Actions outputs + a job summary, and
# exits non-zero when physics violations are found according to --fail-on.
#
# We invoke the CLI with --json so it emits a machine-readable result and
# returns exit 0 on a successful request; the pass/fail decision is made
# here so it is explicit and independent of the CLI's own exit convention.
# A failed request (no JSON on stdout) fails the step.
#
set -euo pipefail

FILE=""
ENGINE="validate"
SIM_TYPE=""
CONDITIONS=""
FAIL_ON="failed"

while [ $# -gt 0 ]; do
  case "$1" in
    --file)        FILE="$2"; shift 2 ;;
    --engine)      ENGINE="$2"; shift 2 ;;
    --type)        SIM_TYPE="$2"; shift 2 ;;
    --conditions)  CONDITIONS="$2"; shift 2 ;;
    --fail-on)     FAIL_ON="$2"; shift 2 ;;
    *) echo "::error::unknown argument: $1"; exit 2 ;;
  esac
done

if [ -z "$FILE" ]; then
  echo "::error::--file is required"; exit 2
fi
if [ ! -f "$FILE" ]; then
  echo "::error::file not found: $FILE"; exit 2
fi

RESULT="simapi-result.json"

# Assemble the CLI command.
ARGS=("$ENGINE" "$FILE" "--json")
[ -n "$SIM_TYPE" ] && [ "$ENGINE" = "validate" ] && ARGS+=("--type" "$SIM_TYPE")
[ -n "$CONDITIONS" ] && [ "$ENGINE" = "dimensional" ] && ARGS+=("--conditions" "$CONDITIONS")

echo "+ simapi ${ARGS[*]}"

# Run. Capture stdout (the JSON) to the result file; let stderr flow to logs.
set +e
simapi "${ARGS[@]}" >"$RESULT"
CLI_RC=$?
set -e

# A successful --json run prints a JSON object. If the request failed, the CLI
# prints an error to stderr and emits no JSON — surface that and fail the step.
if [ ! -s "$RESULT" ] || ! node -e "JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))" "$RESULT" 2>/dev/null; then
  echo "::error::SimAPI produced no valid JSON (CLI exit ${CLI_RC}). See logs above."
  exit 1
fi

# Parse the verdict. Handle both the summarized (validate) and raw
# (dimensional) shapes; fall back sensibly when a field is absent.
read -r STATUS TRAINING IMPOSSIBLE INCONSISTENT < <(node -e '
  const r = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
  const impossible   = Number(r.n_impossible ?? r.impossible ?? 0);
  const inconsistent = Number(r.n_inconsistent ?? r.inconsistent ?? 0);
  let status = r.status;
  if (!status) status = impossible > 0 ? "failed" : inconsistent > 0 ? "warning" : "passed";
  const training = (r.training_ready ?? (impossible === 0)) ? "true" : "false";
  process.stdout.write([status, training, impossible, inconsistent].join(" "));
' "$RESULT")

{
  echo "status=$STATUS"
  echo "training-ready=$TRAINING"
  echo "impossible=$IMPOSSIBLE"
  echo "inconsistent=$INCONSISTENT"
  echo "result-path=$RESULT"
} >> "${GITHUB_OUTPUT:-/dev/null}"

{
  echo "## SimAPI validation"
  echo ""
  echo "| Field | Value |"
  echo "|---|---|"
  echo "| File | \`$FILE\` |"
  echo "| Engine | $ENGINE |"
  echo "| Verdict | **$STATUS** |"
  echo "| Training ready | $TRAINING |"
  echo "| Impossible rows | $IMPOSSIBLE |"
  echo "| Inconsistent rows | $INCONSISTENT |"
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"

echo "verdict=$STATUS training_ready=$TRAINING impossible=$IMPOSSIBLE inconsistent=$INCONSISTENT"

# Gate.
case "$FAIL_ON" in
  never)
    exit 0
    ;;
  warning)
    if [ "$IMPOSSIBLE" -gt 0 ] || [ "$INCONSISTENT" -gt 0 ] || [ "$STATUS" != "passed" ]; then
      echo "::error::SimAPI gate failed (fail-on=warning): $IMPOSSIBLE impossible, $INCONSISTENT inconsistent, verdict $STATUS"
      exit 1
    fi
    ;;
  failed|*)
    if [ "$IMPOSSIBLE" -gt 0 ] || [ "$STATUS" = "failed" ]; then
      echo "::error::SimAPI gate failed (fail-on=failed): $IMPOSSIBLE impossible rows, verdict $STATUS"
      exit 1
    fi
    ;;
esac

echo "SimAPI gate passed."
exit 0
