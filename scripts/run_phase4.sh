#!/usr/bin/env bash
# Phase 4 driver: E7 library-cost sweep (966 Z2xZ2 reps) + any eval/phase4_*.py analyses.
# Idempotent/resumable; safe to re-run after reboot.
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
mkdir -p logs results
LOG=logs/run_phase4.log
exec 9>"$ROOT/logs/run_phase4.lock"
if ! flock -n 9; then echo "$(date -Is) another run_phase4 is active; exiting" >> "$LOG"; exit 0; fi
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
PY=$ROOT/pyenv/bin/python
log "run_phase4 invoked"
log "A-fix skipped: UNKNOWN/LB-unproven ha_sum/ha_joint/mul instances are settled by the E14 S=10 exhaustive GPU enumeration (sizes <= 10 exact, otherwise > 10); the 1,200 s CP-SAT retries would take ~1 day"
log "E7: library costs on Z2xZ2 representatives"
$PY synth/run_libcost.py --enum results/enumerate.csv --out results --reps4 --procs 16 --solver-workers 2 --time-limit 300 --slack 3 >> logs/phase4_libcost.log 2>&1
log "E7 done"
for s in eval/phase4_*.py; do
  [ -f "$s" ] || continue
  out="results/$(basename "$s" .py).done"
  if [ -f "$out" ]; then log "skip $s"; continue; fi
  log "run $s"; $PY "$s" >> "logs/$(basename "$s" .py).log" 2>&1 && touch "$out" && log "done $s" || log "FAIL $s"
done
log "run_phase4 finished"
