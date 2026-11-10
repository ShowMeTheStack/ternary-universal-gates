#!/usr/bin/env bash
# Control script for the universality pipeline (run ON the box so ssh command lines never
# contain process-name patterns). Usage: ./ctl.sh status|stop|start|restart
# start launches the full clean batch (make_batch.sh), which is resumable/idempotent.
ROOT=/extra/universality; cd "$ROOT" || exit 1
status(){ echo "batch $(pgrep -c -f 'bash ./make_batch.sh') runall $(pgrep -c -f 'bash ./run_all.sh') univ $(pgrep -c -f 'target/release/univ') wrapper $(pgrep -c -f 'bash ./run_pipeline.sh') phase2 $(pgrep -c -f 'bash ./run_phase2.sh') phase4 $(pgrep -c -f 'bash ./run_phase4.sh') sweep $(pgrep -c -f 'synth/run_sweep') libcost $(pgrep -c -f 'synth/run_libcost') workers $(pgrep -c -f forkserver) lockB[$(fuser logs/batch.lock 2>/dev/null)] lock1[$(fuser logs/run_all.lock 2>/dev/null)] lock2[$(fuser logs/run_phase2.lock 2>/dev/null)] lock4[$(fuser logs/run_phase4.lock 2>/dev/null)]"; }
stop(){ pkill -f 'bash ./make_batch.sh'; pkill -f 'make_batch.sh'; pkill -f 'queue_pipeline.sh'; pkill -f 'bash ./run_pipeline.sh'; pkill -f 'run_pipeline.sh'; sleep 1
        pkill -f 'bash ./run_all.sh'; pkill -f 'bash ./run_phase2.sh'; pkill -f 'bash ./run_phase4.sh'; sleep 1
        pkill -9 -f 'target/release/univ'; pkill -9 -f 'synth/run_sweep'; pkill -9 -f 'synth/run_libcost'; pkill -9 -f 'eval/phase4_'; pkill -9 -f 'eval/phase1_'; pkill -9 -f 'eval/phase2_'; pkill -9 -f forkserver; pkill -9 -f resource_tracker; sleep 3
        echo "$(date -Is) ctl stop" >> logs/pipeline.log; }
start(){ mkdir -p logs; echo "$(date -Is) ctl start (make_batch.sh)" >> logs/pipeline.log; setsid nohup ./make_batch.sh > logs/batch_launcher.out 2>&1 < /dev/null & disown; sleep 3; }
case "${1:-status}" in status) status;; stop) stop; status;; start) start; status;; restart) stop; start; status;; esac
