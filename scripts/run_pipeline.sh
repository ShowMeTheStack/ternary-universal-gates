#!/usr/bin/env bash
# Whole-pipeline wrapper: waits for any running Phase 2 to finish, then (re)runs Phase 2
# (no-op if complete) and Phase 4. Installed as the @reboot cron entry.
ROOT=/extra/universality; cd "$ROOT" || exit 1
mkdir -p logs
echo "$(date -Is) pipeline invoked" >> logs/pipeline.log
while fuser logs/run_phase2.lock >/dev/null 2>&1; do sleep 300; done
./run_phase2.sh >> logs/pipeline.log 2>&1
while fuser logs/run_phase4.lock >/dev/null 2>&1; do sleep 300; done
./run_phase4.sh >> logs/pipeline.log 2>&1
echo "$(date -Is) pipeline finished" >> logs/pipeline.log
