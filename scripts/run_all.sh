#!/usr/bin/env bash
# Idempotent, resumable driver for the universality experiments.
# Safe to re-run at any time (e.g. from @reboot cron): every step is skipped
# when its output exists; long steps checkpoint per chunk inside the binary.
set -u
ROOT=/extra/universality
cd "$ROOT" || exit 1
mkdir -p logs results
LOG=logs/run_all.log
exec 9>"$ROOT/logs/run_all.lock"
if ! flock -n 9; then echo "$(date -Is) another run_all is active; exiting" >> "$LOG"; exit 0; fi
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
step(){ # step NAME OUTPUT CMD...
  local name=$1 out=$2; shift 2
  if [ -s "$out" ]; then log "skip $name ($out exists)"; return 0; fi
  log "start $name"
  local t0=$(date +%s)
  if "$@" >> "logs/$name.log" 2>&1; then
    log "done  $name in $(( $(date +%s) - t0 ))s"
  else
    log "FAIL  $name (exit $?) — see logs/$name.log"; return 1
  fi
}
log "run_all invoked (host $(hostname), uptime $(cut -d' ' -f1 /proc/uptime)s)"
[ -f results/meta.json ] || {
  python3 -I - <<'EOF' > results/meta.json
import json,platform,subprocess,datetime
def sh(c):
    try: return subprocess.check_output(c,shell=True,text=True).strip()
    except Exception as e: return str(e)
print(json.dumps({
 "host":platform.node(),"kernel":platform.release(),
 "cpu":sh("lscpu | grep 'Model name' | sed 's/.*: *//'"),
 "threads":sh("nproc"),"mem":sh("free -h | awk '/Mem/{print $2}'"),
 "rustc":sh("rustc --version"),"cargo":sh("cargo --version"),
 "python":platform.python_version(),
 "governor":sh("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null"),
 "created":datetime.datetime.now().isoformat()},indent=2))
EOF
}
# build if needed
if [ ! -x target/release/univ ] || [ src/main.rs -nt target/release/univ ]; then
  log "building"; cargo build --release >> logs/build.log 2>&1 || { log "BUILD FAILED"; exit 1; }
fi
B=./target/release/univ
step E1_enumerate  results/enumerate.csv    $B enumerate  results/enumerate.csv              || exit 1
step E2_orbits     results/orbits.json      $B orbits     results/enumerate.csv results/orbits.json
step E11_lowerbound results/lower_bounds.json $B lowerbound results/lower_bounds.json
step E4_synth_ha   results/synth_ha.csv     $B synth      results/enumerate.csv results/synth_ha.csv
step E3_timing     results/timing.json      $B timing 10  results/timing.json
step P1_report     results/phase1_report.md python3 -I eval/phase1_report.py
log "run_all finished"
