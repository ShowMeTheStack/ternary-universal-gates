#!/usr/bin/env python3
"""E14 soundness checks (size-spectrum stage): compare GPU spectrum JSONs with
(a) their --nosym twins (must be identical), (b) CP-SAT Stage A sizes in results/synth/{ha_sum,ha_carry,mul}
(OPTIMAL => equal; otherwise GPU <= CP-SAT UB), (c) E4 DP sizes in results/synth_ha.csv (GPU <= Gs_dag/Gc_dag).
Usage: validate.py results/gpu_spectrum_S8 [results]   (stdlib only; never reads *_pre_batch_*)"""
import json, os, sys, csv, glob
D = sys.argv[1]; R = sys.argv[2] if len(sys.argv) > 2 else "results"
assert "pre_batch" not in D and "pre_batch" not in R
files = sorted(glob.glob(f"{D}/*.json"))
spec = {}
for f in files:
    if f.endswith(".nosym.json"): continue
    j = json.load(open(f)); spec[j["gate"]] = j
print(f"{len(spec)} gate spectra in {D}")
# (a) nosym twins
bad = 0; n = 0
for f in glob.glob(f"{D}/*.nosym.json"):
    j = json.load(open(f)); g = j["gate"]
    if g in spec:
        n += 1
        if j["minsize"] != spec[g]["minsize"] or j["hist"] != spec[g]["hist"]:
            bad += 1; print(f"  SYMMETRY MISMATCH g{g}")
print(f"(a) nosym twins compared: {n}, mismatches: {bad}")
# (b) CP-SAT
def cp(task, g):
    p = f"{R}/synth/{task}/{g}.json"
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None
for task, key in [("ha_sum", "h_sum"), ("ha_carry", "h_carry"), ("mul", "mul")]:
    eq = ne = le = gt = miss = 0
    for g, j in spec.items():
        c = cp(task, g)
        if c is None: miss += 1; continue
        s = j[key]; S = j["S"]
        size = c.get("size"); st = c.get("status")
        if size is None: miss += 1; continue
        if s == -1:
            if size <= S: gt += 1; print(f"  {task} g{g}: CP-SAT {st} size {size} <= S={S} but GPU did not reach it!")
            continue
        if st == "OPTIMAL":
            if s == size: eq += 1
            else: ne += 1; print(f"  {task} g{g}: GPU {s} != CP-SAT OPTIMAL {size}")
        else:
            if s <= size: le += 1
            else: gt += 1; print(f"  {task} g{g}: GPU {s} > CP-SAT UB {size} ({st})")
    print(f"(b) {task}: equal-to-OPTIMAL {eq}, MISMATCH {ne}, <=UB {le}, VIOLATION {gt}, no CP-SAT data {miss}")
# (c) E4 DP upper bounds
p = f"{R}/synth_ha.csv"
if os.path.exists(p):
    viol = n = 0
    for r in csv.DictReader(open(p)):
        g = int(r["gate"]); j = spec.get(g)
        if not j: continue
        for col, key in [("Gs_dag", "h_sum"), ("Gc_dag", "h_carry")]:
            if r.get(col):
                n += 1
                if j[key] != -1 and j[key] > int(r[col]): viol += 1; print(f"  E4 g{g}: GPU {key} {j[key]} > DP {r[col]}")
    print(f"(c) E4 DP bounds checked: {n}, violations: {viol}")
# summary stats
S = next(iter(spec.values()))["S"] if spec else 0
full = [g for g, j in spec.items() if j["reached"] == 19683]
print(f"gates reaching all 19,683 functions within S={S}: {len(full)}")
if full:
    diam = {}
    for g in full:
        h = spec[g]["hist"]; diam[g] = max(i for i, v in enumerate(h) if v)
    from collections import Counter
    print("size-diameter distribution:", sorted(Counter(diam.values()).items()))
print("seconds per gate: min %.1f median %.1f max %.1f" % tuple(sorted(j["seconds"] for j in spec.values())[i] for i in (0, len(spec) // 2, len(spec) - 1)) if spec else "")
