#!/usr/bin/env python3
"""Clean-or-redo exposure checker . For every load-sensitive result file
written after the first foreign container (2026-11-04 08:14:38 IST), reconstruct its run interval
[mtime - wall - MARGIN, mtime + MARGIN] and intersect it with every foreign-activity interval from
(a) the podman container start/died events exported from journald and (b) the 30-s sampler
(any sample with foreign% > 0 or containers > 0 covers [t-45 s, t+45 s]). Overlapping files are
MOVED (never deleted) to <discard>/<iteration>/<relative path> so the resumable drivers recompute them.
Usage: exposure_check.py <results_dir> <events_file> <sampler_log> <discard_dir> [--dry]
Prints a summary and exits 0 if nothing was exposed, 1 if files were moved (another pass is needed).
"""
import sys, os, json, glob, datetime as dt, shutil
R, EV, SL, DISC = sys.argv[1:5]; DRY = "--dry" in sys.argv
MARGIN = dt.timedelta(seconds=600)   # wide boundary: 10 min on every side
T0 = dt.datetime.fromisoformat("2026-11-04T08:14:38+05:30")   # first foreign container (journald); files older than this are clean
tz = T0.tzinfo
def parse(ts):
    d = dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=tz)
# ---- foreign intervals
iv = []
start = {}
for line in open(EV):
    p = line.split()
    if len(p) < 3: continue
    t, s, cid = parse(p[0]), p[1], p[2]
    if s == "start": start[cid] = t
    elif cid in start: iv.append((start.pop(cid) - MARGIN, t + MARGIN))
now = dt.datetime.now(tz)
for cid, t in start.items(): iv.append((t - MARGIN, now + MARGIN))      # still running
if os.path.exists(SL):
    for line in open(SL):
        p = line.split()
        if len(p) < 4: continue
        try:
            t = parse(p[0]); f = float([x for x in p if x.startswith("foreign%=")][0].split("=")[1])
            c = int([x for x in p if x.startswith("containers=")][0].split("=")[1])
        except Exception: continue
        other_foreign = ('top_other=' in line) and ('target/release/univ' not in line)   # the batch's own single-thread timing binary (univ timing) is ours, not foreign
        if f > 0 or c > 0 or other_foreign: iv.append((t - dt.timedelta(seconds=45) - MARGIN, t + dt.timedelta(seconds=45) + MARGIN))
iv.sort(); merged = []
for a, b in iv:
    if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(merged[-1][1], b))
    else: merged.append((a, b))
print(f"foreign intervals (merged, with ±{MARGIN.seconds}s margin): {len(merged)}, total {sum((b-a).total_seconds() for a,b in merged)/3600:.2f} h")
def exposed(a, b): return any(x < b and a < y for x, y in merged)
# ---- result files to check: everything load-sensitive written after T0
WALL_KEYS = ("wall_size", "wall", "seconds", "wall_s")
cands = []
for pat in ("synth/fa_carry/*.json", "synth/fa_joint/*.json", "synth/ha_sum/*.json", "synth/ha_joint/*.json", "synth/mul/*.json", "libcost/*.json", "timing.json"):
    cands += glob.glob(os.path.join(R, pat))
moved = []; checked = 0; detail = []
it_dir = os.path.join(DISC, now.strftime("pass_%Y%m%d_%H%M%S"))
for f in cands:
    mt = dt.datetime.fromtimestamp(os.path.getmtime(f), tz)
    if mt < T0: continue
    checked += 1
    wall = None
    try:
        j = json.load(open(f))
        if isinstance(j, dict):
            for k in WALL_KEYS:
                if isinstance(j.get(k), (int, float)): wall = float(j[k]); break
            if wall is None and "time_limit" in j: wall = 2.5 * float(j["time_limit"])   # LB loop + UB search upper estimate
        elif isinstance(j, list) and f.endswith("timing.json"): wall = 600.0
    except Exception:
        wall = 900.0                                     # unreadable: treat as long
    if wall is None: wall = 900.0
    a, b = mt - dt.timedelta(seconds=wall) - MARGIN, mt + MARGIN
    if exposed(a, b):
        rel = os.path.relpath(f, R); dest = os.path.join(it_dir, rel)
        moved.append(rel)
        hit = [(x, y) for x, y in merged if x < b and a < y][0]
        detail.append(f"{rel}\tjob[{a.isoformat(timespec='seconds')} .. {b.isoformat(timespec='seconds')}] wall={wall:.0f}s\toverlaps foreign[{hit[0].isoformat(timespec='seconds')} .. {hit[1].isoformat(timespec='seconds')}]")
        if not DRY:
            os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.move(f, dest)
            if f.endswith("timing.json"):
                td = os.path.join(R, ".timing_done")
                if os.path.exists(td): shutil.move(td, os.path.join(it_dir, ".timing_done"))
            done = os.path.join(R, os.path.dirname(rel) + ".done")
print(f"checked {checked} load-sensitive files written after {T0.isoformat()}; exposed: {len(moved)}{' (dry run)' if DRY else ' -> moved to ' + it_dir}")
by = {}
for m in moved: by[m.split('/')[0] + '/' + m.split('/')[1] if '/' in m else m] = by.get(m.split('/')[0] + '/' + m.split('/')[1] if '/' in m else m, 0) + 1
print("by directory:", by)
if moved and not DRY:
    with open(os.path.join(it_dir, "MOVED.txt"), "w") as fo: fo.write("\n".join(moved) + "\n")
    with open(os.path.join(it_dir, "TAINTED_detail.tsv"), "w") as fo: fo.write("\n".join(detail) + "\n")
    with open(os.path.join(os.path.dirname(it_dir.rstrip('/')), "tainted_jobs_all_passes.log"), "a") as fo:
        fo.write(f"# {now.isoformat(timespec='seconds')} pass dir {it_dir}: {len(moved)} tainted (margin {MARGIN.seconds}s)\n" + "\n".join(detail) + "\n")
sys.exit(1 if moved else 0)
