#!/usr/bin/env bash
# Phase 2 driver (exact synthesis sweeps). Idempotent and resumable: run_sweep.py writes one
# JSON per (gate, task) and skips existing ones, so this can be re-invoked after a reboot.
set -u
ROOT=/extra/universality
cd "$ROOT" || exit 1
mkdir -p logs results/synth
LOG=logs/run_phase2.log
exec 9>"$ROOT/logs/run_phase2.lock"
if ! flock -n 9; then echo "$(date -Is) another run_phase2 is active; exiting" >> "$LOG"; exit 0; fi
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
PY=$ROOT/pyenv/bin/python
ENUM=results/enumerate.csv
[ -s "$ENUM" ] || { log "missing $ENUM (run Phase 1 first)"; exit 1; }
log "run_phase2 invoked (host $(hostname), uptime $(cut -d' ' -f1 /proc/uptime)s)"

# Stage 0: k = 4 enumeration (E12), resumable per 2^20-gate range
if [ -s results/k4.json ]; then log "skip stage 0 (results/k4.json exists)"; else
  log "stage 0: k=4 enumeration (4^16 gates, Davies criterion, Burnside S4xZ2)"
  ./target/release/univ k4 results/k4 >> logs/phase2_stage0.log 2>&1 && log "stage 0 done" || log "stage 0 FAILED"
fi

# Stage A: cheap exact tasks on ALL 3,774 universal gates (HA sum/carry/joint, MUL).
#   32 threads: 16 procs x 2 solver workers.
log "stage A: ha_sum,ha_carry,ha_joint,mul on all universal gates"
$PY synth/run_sweep.py --enum $ENUM --out results/synth --tasks ha_sum,ha_carry \
    --procs 16 --solver-workers 2 --time-limit 300 --depth >> logs/phase2_stageA.log 2>&1
$PY synth/run_sweep.py --enum $ENUM --out results/synth --tasks ha_joint,mul \
    --procs 16 --solver-workers 2 --time-limit 120 >> logs/phase2_stageA.log 2>&1
log "stage A done"

# Stage B: FA tasks on one representative per Z2xZ2 class (966 classes), bounds mode.
#   16 procs x 2 solver workers; 10 min per instance budget (est. 1-2 days total).
log "stage B: fa_sum,fa_carry,fa_joint on Z2xZ2 representatives"
$PY synth/run_sweep.py --enum $ENUM --out results/synth --tasks fa_carry,fa_joint --reps4 \
    --procs 16 --solver-workers 2 --time-limit 300 >> logs/phase2_stageB.log 2>&1
log "stage B done"

# Stage C: aggregate
$PY eval/phase2_report.py >> logs/phase2_report.log 2>&1 && log "report written" || log "report FAILED"
log "run_phase2 finished"
