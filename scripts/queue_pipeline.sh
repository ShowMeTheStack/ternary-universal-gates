#!/usr/bin/env bash
# Re-invoke the pipeline once the current run finishes (so Stage B runs after Phase 4).
cd /extra/universality || exit 1
until tail -1 logs/pipeline.log | grep -q "pipeline finished"; do sleep 300; done
echo "$(date -Is) queued second pipeline invocation starting" >> logs/pipeline.log
./run_pipeline.sh
