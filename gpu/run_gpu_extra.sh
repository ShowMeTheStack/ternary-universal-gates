#!/usr/bin/env bash
# E14 follow-on stage (size-spectrum stage): S=10 on every universal gate whose CP-SAT ha_sum /
# ha_joint / mul status is not OPTIMAL after Phase 4 (so that brute force settles them), written
# into the same results/gpu_spectrum_S10 directory (skip-if-exists). Waits for run_gpu.sh to
# finish ("run_gpu finished" in logs/gpu_run.log). Resumable; separate from run_gpu.sh so the
# running waiter script is never edited in place.
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
mkdir -p logs
exec 6>"$ROOT/logs/gpu_extra.lock"
if ! flock -n 6; then echo "$(date -Is) another run_gpu_extra is active; exiting" >> logs/gpu_run.log; exit 0; fi
log(){ echo "$(date -Is) [extra] $*" >> logs/gpu_run.log; }
log "run_gpu_extra invoked"
until grep -q "run_gpu finished" logs/gpu_run.log 2>/dev/null; do sleep 300; done
OUT=results/gpu_spectrum_S10; mkdir -p "$OUT"
if [ -f "$OUT/.done_unknown" ]; then log "skip S=10 unknown stage (done)"; exit 0; fi
UNK=$(python3 -I - <<'PY'
import json, glob, os
g = set()
for t in ("ha_sum", "ha_joint", "mul"):
    for f in glob.glob(f"results/synth/{t}/*.json"):
        try: j = json.load(open(f))
        except Exception: continue
        if j.get("status") != "OPTIMAL": g.add(int(os.path.basename(f).split(".")[0]))
print(",".join(map(str, sorted(g))))
PY
)
N=$(echo "$UNK" | tr ',' '\n' | grep -c .)
log "S=10 on $N non-OPTIMAL gates"
[ "$N" -gt 0 ] || { touch "$OUT/.done_unknown"; log "nothing to do"; exit 0; }
for d in "$OUT"/*.lock; do [ -d "$d" ] && rmdir "$d"; done
./gpu/spectrum --enum results/enumerate.csv --out "$OUT" --smax 10 --device 0 --gates "$UNK" >> logs/gpu_spectrum_S10_unknown_d0.log 2>&1 &
p0=$!
./gpu/spectrum --enum results/enumerate.csv --out "$OUT" --smax 10 --device 1 --gates "$UNK" >> logs/gpu_spectrum_S10_unknown_d1.log 2>&1 &
p1=$!
wait $p0; wait $p1
missing=0; for g in $(echo "$UNK" | tr ',' ' '); do [ -f "$OUT/$g.json" ] || missing=$((missing+1)); done
log "S=10 unknown stage finished: missing $missing of $N"
[ "$missing" -eq 0 ] && touch "$OUT/.done_unknown"
log "run_gpu_extra finished"
