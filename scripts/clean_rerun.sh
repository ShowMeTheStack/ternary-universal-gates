#!/usr/bin/env bash
# CLEAN-OR-REDO orchestrator Guarantees that every load-sensitive result
# (Stage B fa_carry/fa_joint, Phase 4 A-fix/E7, TIMING) was computed with no foreign container active:
#   1. stop the batch; move all fa_joint results and fa_carry results written after 07:45 to the discard dir
#   2. wait until the sampler shows 0 foreign CPU and 0 containers for 10 consecutive minutes
#   3. ./ctl.sh start  (make_batch resumes: Phase 1/Stage 0/Stage A skipped, Stage B recomputes, Phase 4, TIMING)
#   4. when "BATCH finished (all)": exposure_check moves every result whose run interval overlapped foreign
#      activity; if any -> wait for quiet, restart, repeat (max 6 passes)
#   5. write results/.clean_verified and log "CLEAN-OR-REDO finished"
# Old files are MOVED to /extra/universality/discard_stageB_<stamp>/ (never deleted). Resumable (cron @reboot).
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
mkdir -p logs
exec 3>"$ROOT/logs/clean_rerun.lock"
if ! flock -n 3; then echo "$(date -Is) another clean_rerun is active; exiting" >> logs/clean_rerun.log; exit 0; fi
log(){ echo "$(date -Is) $*" | tee -a logs/clean_rerun.log; }
DISC_FILE=logs/clean_rerun.discard_dir
if [ -f "$DISC_FILE" ]; then DISC=$(cat "$DISC_FILE"); else DISC="$ROOT/discard_stageB_$(date +%Y%m%d_%H%M%S)"; echo "$DISC" > "$DISC_FILE"; fi
mkdir -p "$DISC"
export_events(){ journalctl --since "2026-11-03 19:30" -o short-iso --no-pager 2>/dev/null | grep -E "container (start|died)" | sed -E "s/^([0-9T:+-]+) .*container (start|died) ([0-9a-f]+) .*/\1 \2 \3/" > logs/fload1_container_events_ids.txt; }
wait_quiet(){ # 20 consecutive sampler lines (10 min) with foreign%=0 and containers=0
  log "waiting for a quiet box (10 min with no foreign CPU / containers)"
  while true; do
    pgrep -f "[f]load1_sampler" >/dev/null || { setsid nohup python3 -I logs/fload1_sampler.py >/dev/null 2>&1 < /dev/null & sleep 2; }
    n=$(tail -20 logs/fload1_sampler.log 2>/dev/null | grep -c "foreign%=0 (n=0) .* containers=0")
    [ "$n" -ge 20 ] && break
    sleep 60
  done
  log "box quiet (load $(cut -d' ' -f1 /proc/loadavg)) -> go"
}
if [ ! -f logs/clean_rerun.step1_done ]; then
  log "STEP 1: stopping the batch and discarding exposed Stage B results"
  ./ctl.sh stop >> logs/clean_rerun.log 2>&1
  mkdir -p "$DISC/initial/synth/fa_joint" "$DISC/initial/synth/fa_carry"
  nj=$(ls results/synth/fa_joint/*.json 2>/dev/null | wc -l); mv results/synth/fa_joint/*.json "$DISC/initial/synth/fa_joint/" 2>/dev/null
  nc=0; for f in $(find results/synth/fa_carry -name '*.json' -newermt '2026-11-04 07:45:00'); do mv "$f" "$DISC/initial/synth/fa_carry/"; nc=$((nc+1)); done
  rm -f results/synth/fa_joint/*.lock results/synth/fa_carry/*.lock 2>/dev/null
  log "moved $nj fa_joint and $nc fa_carry (mtime >= 07:45) result files to $DISC/initial; fa_carry kept: $(ls results/synth/fa_carry/*.json | wc -l)"
  touch logs/clean_rerun.step1_done
fi
pass=0
while [ $pass -lt 6 ]; do
  pass=$((pass+1))
  wait_quiet
  if ! grep -q "BATCH finished (all)" logs/batch.log 2>/dev/null || [ -n "$(ls -d "$DISC"/pass_* 2>/dev/null)" ] ; then
    # (re)start the batch if it is not running
    if [ "$(pgrep -c -f '[b]ash ./make_batch.sh')" -eq 0 ]; then
      # a finished batch must be re-armed: remove the "finished" marker lines' effect by relaunching make_batch (it is idempotent)
      log "pass $pass: starting the batch (make_batch.sh resumes missing work)"
      ./ctl.sh start >> logs/clean_rerun.log 2>&1
    fi
  fi
  log "pass $pass: waiting for 'BATCH finished (all)' (this pass's run)"
  marker=$(grep -c "BATCH finished (all)" logs/batch.log 2>/dev/null)
  while [ "$(grep -c "BATCH finished (all)" logs/batch.log 2>/dev/null)" -le "$marker" ] && pgrep -f "[b]ash ./make_batch.sh" >/dev/null; do sleep 300; done
  sleep 60
  export_events
  log "pass $pass: exposure check"
  if python3 -I eval/exposure_check.py results logs/fload1_container_events_ids.txt logs/fload1_sampler.log "$DISC" >> logs/clean_rerun.log 2>&1; then
    log "pass $pass: no exposed results -> CLEAN"
    date -Is > results/.clean_verified
    log "CLEAN-OR-REDO finished"
    exit 0
  else
    log "pass $pass: exposed results moved -> another pass"
  fi
done
log "CLEAN-OR-REDO gave up after $pass passes (foreign load keeps returning) — needs the user"
exit 2
