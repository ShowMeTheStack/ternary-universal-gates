#!/usr/bin/env python3
"""E7: cheapest realisation of each universal gate in the ternary cell library
L** = {STI, NTI, PTI, TNAND, TNOR, CONST1, INC, DEC}. Resumable: results/libcost/<gate>.json.
Reports min cell count (status), and min transistor cost under each cost variant in
data/cell_costs.json (cost-minimisation over m in [min_cells, min_cells+slack]).

Usage: run_libcost.py --enum results/enumerate.csv --out results [--gates 451,8431]
       [--reps4] [--procs 16] [--solver-workers 2] [--time-limit 300] [--slack 3]
"""
import argparse, csv, json, os, sys, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exact import Lib, min_size, build, gate_table_from_label, simulate
from libs import LIB_L, un2

COSTS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cell_costs.json")))["variants"]
# L** = L* ∪ {INC, DEC} (Etiemble's successor/predecessor cells, 8 T with two supplies)
from libs import INC, DEC
NAMES = ["STI", "NTI", "PTI", "TNAND", "TNOR", "C1", "INC", "DEC"]
TABLES = [LIB_L["STI"][0], LIB_L["NTI"][0], LIB_L["PTI"][0], LIB_L["TNAND"][0], LIB_L["TNOR"][0], un2([1, 1, 1]), un2(INC), un2(DEC)]
ARITY = [1, 1, 1, 2, 2, 0, 1, 1]
def lib_for(variant):
    c = COSTS[variant]
    return Lib(3, TABLES, NAMES, [c["STI"], c["NTI"], c["PTI"], c["TNAND"], c["TNOR"], c["CONST1"], c["SUCC"], c["PRED"]], ARITY)

def solve_one(args):
    gate, outdir, time_limit, workers, slack = args
    path = os.path.join(outdir, "libcost", f"{gate}.json")
    if os.path.exists(path): return gate, "skip"
    tt = gate_table_from_label(gate)
    L = lib_for("lin2011")
    t0 = time.time()
    r = min_size(L, 2, [tt], lo=1, hi=20, time_limit=time_limit, workers=workers)
    rec = {"gate": gate, "min_cells": r.size, "min_cells_status": r.status, "lb_cells": r.bound_lb,
           "cells_circuit": r.gates, "wall": None, "costs": {}}
    if r.size is not None:
        # cost-minimise under the primary variant only (m and m+1, short budget); evaluate the
        # resulting circuits under the other variants by table lookup (upper bounds for those).
        cands = [(r.gates, r.outputs)]
        Lp = lib_for("lin2011")
        for m in range(r.size, r.size + min(slack, 1) + 1):
            rr = build(Lp, 2, [tt], m, None, minimize="cost", time_limit=min(120, time_limit), workers=workers)
            if rr.status in ("OPTIMAL", "FEASIBLE"): cands.append((rr.gates, rr.outputs))
        for v in COSTS:
            Lv = lib_for(v); cost = {n: c for n, c in zip(Lv.names, Lv.costs)}; best = None
            for g, o in cands:
                assert simulate(Lv, 2, g, o) == [tt]
                c = sum(cost[t] for t, _, _ in g)
                if best is None or c < best[0]: best = (c, g, o)
            rec["costs"][v] = {"transistors": best[0], "cells": len(best[1]), "status": "min over found circuits", "circuit": best[1]}
    rec["wall"] = round(time.time() - t0, 1)
    tmp = path + ".tmp"; json.dump(rec, open(tmp, "w")); os.replace(tmp, path)
    return gate, rec["min_cells_status"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enum", required=True); ap.add_argument("--out", default="results")
    ap.add_argument("--gates", default=None); ap.add_argument("--reps4", action="store_true")
    ap.add_argument("--procs", type=int, default=max(1, mp.cpu_count() // 2))
    ap.add_argument("--solver-workers", type=int, default=2)
    ap.add_argument("--time-limit", type=float, default=300); ap.add_argument("--slack", type=int, default=3)
    a = ap.parse_args()
    gates = []
    seen = set()
    for r in csv.DictReader(open(a.enum)):
        if r["closure_size"] != "19683": continue
        if a.reps4:
            if r["canon4"] in seen: continue
            seen.add(r["canon4"])
        gates.append(int(r["gate"]))
    if a.gates: want = {int(x) for x in a.gates.split(",")}; gates = [g for g in gates if g in want]
    os.makedirs(os.path.join(a.out, "libcost"), exist_ok=True)
    jobs = [(g, a.out, a.time_limit, a.solver_workers, a.slack) for g in gates
            if not os.path.exists(os.path.join(a.out, "libcost", f"{g}.json"))]
    print(f"{len(gates)} gates, {len(jobs)} to do", flush=True)
    t0 = time.time(); done = 0
    with mp.Pool(a.procs) as pool:
        for g, st in pool.imap_unordered(solve_one, jobs, chunksize=1):
            done += 1
            if done % 10 == 0 or done == len(jobs): print(f"[{time.time()-t0:7.0f}s] {done}/{len(jobs)} last g{g} {st}", flush=True)

if __name__ == "__main__":
    main()
