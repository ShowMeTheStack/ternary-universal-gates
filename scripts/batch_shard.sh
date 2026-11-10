#!/usr/bin/env bash
# Multi-host sharding for the CP-SAT sweeps (pre-submission batch). Run ON the primary (mdev).
#   ./batch_shard.sh plan  HOST1[,HOST2...]   # writes shard gate lists results/shards/<host>.txt
#   ./batch_shard.sh push  HOST               # sync code + enumerate.csv + Stage A HA circuits to HOST:/extra/universality (or ~/universality)
#   ./batch_shard.sh run   HOST TASKS         # start run_sweep on HOST for its shard (detached, resumable)
#   ./batch_shard.sh pull  HOST               # rsync HOST's results/synth back here (merge by file name)
# Shards are assigned round-robin over the 966 Z2xZ2 representatives (fa_*) or all 3,774
# gates (ha_*/mul) by sorted gate label, so every host gets a comparable mix of hard and
# easy instances. Budgets are identical on every host; the paper notes the host per record
# is NOT stored, so hosts should be of comparable speed (mdev, 9900K), not laptops.
set -u
ROOT=/extra/universality; cd "$ROOT" || exit 1
cmd=${1:-}; shift || true
case "$cmd" in
plan)
  IFS=, read -r -a hosts <<< "${1:?hosts}"; hosts=("mdev" "${hosts[@]}")
  mkdir -p results/shards
  python3 - "${hosts[@]}" <<'PY'
import csv, sys
hosts = sys.argv[1:]
rows = [r for r in csv.DictReader(open("results/enumerate.csv")) if r["closure_size"] == "19683"]
allg = sorted(int(r["gate"]) for r in rows)
seen, reps = set(), []
for r in sorted(rows, key=lambda r: int(r["gate"])):
    if r["canon4"] not in seen: seen.add(r["canon4"]); reps.append(int(r["gate"]))
for kind, gl in (("all", allg), ("reps4", reps)):
    for i, h in enumerate(hosts):
        mine = [g for j, g in enumerate(gl) if j % len(hosts) == i]
        open(f"results/shards/{h}.{kind}.txt", "w").write(",".join(map(str, mine)) + "\n")
        print(kind, h, len(mine))
PY
  ;;
push)
  H=${1:?host}; D=$(ssh "$H" 'test -d /extra && echo /extra/universality || echo ~/universality')
  ssh "$H" "mkdir -p $D/results/synth $D/synth $D/eval $D/data"
  rsync -az synth/ "$H:$D/synth/"; rsync -az data/ "$H:$D/data/"; rsync -az results/enumerate.csv "$H:$D/results/"
  rsync -az results/synth/ha_sum results/synth/ha_carry results/synth/ha_joint "$H:$D/results/synth/" 2>/dev/null
  rsync -az results/shards "$H:$D/results/"; echo "pushed to $H:$D"
  ;;
run)
  H=${1:?host}; TASKS=${2:?tasks}; D=$(ssh "$H" 'test -d /extra && echo /extra/universality || echo ~/universality')
  kind=all; case "$TASKS" in fa_*) kind=reps4;; esac
  GL=$(cat results/shards/$H.$kind.txt)
  ssh "$H" "cd $D && mkdir -p logs && (setsid nohup \$(test -x pyenv/bin/python && echo pyenv/bin/python || echo python3) synth/run_sweep.py --enum results/enumerate.csv --out results/synth --tasks $TASKS --gates $GL --procs \$(( \$(nproc) / 2 )) --solver-workers 2 --time-limit 300 > logs/shard_$TASKS.log 2>&1 < /dev/null &) ; sleep 2; tail -1 logs/shard_$TASKS.log"
  ;;
pull)
  H=${1:?host}; D=$(ssh "$H" 'test -d /extra && echo /extra/universality || echo ~/universality')
  rsync -az --ignore-existing "$H:$D/results/synth/" results/synth/; echo "pulled from $H"
  ;;
*) echo "usage: $0 plan HOSTS | push HOST | run HOST TASKS | pull HOST";;
esac
