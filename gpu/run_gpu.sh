#!/usr/bin/env bash
# E14 GPU size-spectrum sweep (size-spectrum stage). Waits until the clean CPU batch is completely
# finished ("BATCH finished (all)" in logs/batch.log), then runs, one process per GPU sharing
# the per-gate queue (mkdir claims):
#   stage 1: S=8  all 3,774 universal gates   (~15 min)
#   stage 2: S=9  all 3,774 universal gates   (~3-4 h)
#   stage 3: S=10 the 322 S3xZ2 representatives (histogram/diameter are S3xZ2-invariant) (~8 h)
# Resumable: skip-if-exists per gate, .done marker per stage, stale claims cleared at start.
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
mkdir -p logs
exec 7>"$ROOT/logs/gpu_run.lock"
if ! flock -n 7; then echo "$(date -Is) another run_gpu is active; exiting" >> logs/gpu_run.log; exit 0; fi
log(){ echo "$(date -Is) $*" >> logs/gpu_run.log; }
log "run_gpu invoked"
until grep -q "BATCH finished (all)" logs/batch.log 2>/dev/null; do sleep 300; done
log "batch finished -> E14 starts (load $(cut -d' ' -f1 /proc/loadavg))"
[ -x gpu/spectrum ] || { log "building spectrum"; nvcc -O3 -arch=sm_86 -o gpu/spectrum gpu/spectrum.cu >> logs/gpu_build.log 2>&1 || { log "BUILD FAILED"; exit 1; }; }
stage(){ # stage SMAX GATESARG(optional)
  local S=$1; shift; local OUT=results/gpu_spectrum_S$S; local extra=("$@")
  if [ -f "$OUT/.done" ]; then log "skip S=$S (done)"; return 0; fi
  mkdir -p "$OUT"
  for d in "$OUT"/*.lock; do [ -d "$d" ] && rmdir "$d"; done
  log "stage S=$S start"
  ./gpu/spectrum --enum results/enumerate.csv --out "$OUT" --smax "$S" --device 0 "${extra[@]}" >> "logs/gpu_spectrum_S${S}_d0.log" 2>&1 &
  local p0=$!
  ./gpu/spectrum --enum results/enumerate.csv --out "$OUT" --smax "$S" --device 1 "${extra[@]}" >> "logs/gpu_spectrum_S${S}_d1.log" 2>&1 &
  local p1=$!
  wait $p0; wait $p1
  local n; n=$(ls "$OUT"/*.json 2>/dev/null | wc -l)
  log "stage S=$S finished: $n gate files (expected $EXPECT)"
  [ "$n" -ge "$EXPECT" ] && touch "$OUT/.done"
}
EXPECT=3774; stage 8
EXPECT=3774; stage 9
# S3xZ2 representatives: gates with gate == canon12 among universal gates (closure_size == 19683)
REPS=$(awk -F, 'NR==1{for(i=1;i<=NF;i++){if($i=="closure_size")c=i; if($i=="canon12")r=i}} NR>1 && $c==19683 && $1==$r {print $1}' results/enumerate.csv | paste -sd,)
EXPECT=$(echo "$REPS" | tr ',' '\n' | wc -l); log "S=10 on $EXPECT representatives"
stage 10 --gates "$REPS"
log "run_gpu finished"
