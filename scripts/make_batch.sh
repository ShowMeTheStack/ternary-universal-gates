#!/usr/bin/env bash
# FINAL CLEAN BATCH (pre-submission). Regenerates every number in the paper from scratch.
# Usage (on the box):  ./make_batch.sh          # archives old results/ and logs/, runs everything
#        then, on an IDLE box:  ./make_batch.sh timing   # re-measures the timing items only
# Resumable: if interrupted (power loss), just run ./make_batch.sh again — cron @reboot does
# the same; Stage/phase drivers skip finished work (skip-if-exists on results/ only).
# NO CLOBBER: old results/ and logs/ are moved to *_pre_batch_<stamp>, never deleted.
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
mode="${1:-all}"
mkdir -p logs
exec 8>"$ROOT/logs/batch.lock"
if ! flock -n 8; then echo "$(date -Is) another make_batch is active; exiting" >> logs/batch.log; exit 0; fi
if [ "$mode" = "all" ]; then
  if [ -d results ] && [ ! -f results/.batch_started ]; then
    stamp=$(date +%Y%m%d_%H%M%S)
    mv results "results_pre_batch_$stamp"; echo "archived old results to results_pre_batch_$stamp"
    mv logs "logs_pre_batch_$stamp"; mkdir -p logs; echo "archived old logs to logs_pre_batch_$stamp"
    echo "$(date -Is) archived results/ -> results_pre_batch_$stamp, logs/ -> logs_pre_batch_$stamp" >> logs/batch.log
    exec 8>"$ROOT/logs/batch.lock"; flock -n 8 || exit 0
  fi
  mkdir -p results logs; touch results/.batch_started
  echo "$(date -Is) BATCH start (uptime $(cut -d' ' -f1 /proc/uptime)s, load $(cut -d' ' -f1 /proc/loadavg), governor $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null), users $(who | wc -l))" >> logs/batch.log
  cargo build --release >> logs/build.log 2>&1 || { echo "build failed" >> logs/batch.log; exit 1; }
  ./run_all.sh        >> logs/batch.log 2>&1   # Phase 1: E1 E2 E11 E4 E3 + report
  ./run_pipeline.sh   >> logs/batch.log 2>&1   # Phase 2 (k4, Stage A, Stage B) + Phase 4 (retries, E7, targets, E8, E9)
  echo "$(date -Is) BATCH compute done" >> logs/batch.log
fi
if { [ "$mode" = "all" ] && [ ! -f results/.timing_done ]; } || [ "$mode" = "timing" ]; then
  # Timing items: must run on an idle box. Record the conditions next to the numbers.
  load=$(cut -d' ' -f1 /proc/loadavg)
  echo "$(date -Is) TIMING run: load=$load governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)" >> logs/batch.log
  [ -f results/timing.json ] && cp -n results/timing.json "results/timing_before_$(date +%Y%m%d_%H%M%S).json"
  ./target/release/univ timing 10 results/timing.json >> logs/batch_timing.log 2>&1
  rm -rf results/k4_timing; ( /usr/bin/time -f "k4 wall %e s" ./target/release/univ k4 results/k4_timing ) >> logs/batch_timing.log 2>&1
  python3 - <<PY
import json,os
m=json.load(open("results/meta.json")) if os.path.exists("results/meta.json") else {}
m["timing_conditions"]={"load_1min":"$load","note":"timing.json and k4 wall time measured in this run; box should be idle"}
json.dump(m,open("results/meta.json","w"),indent=2)
PY
  touch results/.timing_done
  echo "$(date -Is) TIMING done" >> logs/batch.log
fi
echo "$(date -Is) BATCH finished ($mode)" >> logs/batch.log
