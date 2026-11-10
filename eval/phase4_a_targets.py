#!/usr/bin/env python3
"""Phase 4 (runs first, alphabetical): library-optimal realisations of the arithmetic
targets over L** (cells + transistors per cost variant): h_sum, h_carry, HA joint, MUL.
These are the denominators of the universality premium. Writes results/libcost_targets.json."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "synth"))
from run_libcost import lib_for, COSTS
from exact import min_size, build, ternary_targets, simulate

T = ternary_targets()
TARGETS = {"h_sum": (2, [T["h_sum"][1]]), "h_carry": (2, [T["h_carry"][1]]),
           "ha_joint": (2, [T["h_sum"][1], T["h_carry"][1]]), "mul": (2, [T["mul"][1]])}
out = {}
for name, (n_in, tts) in TARGETS.items():
    L = lib_for("lin2011"); t0 = time.time()
    r = min_size(L, n_in, tts, lo=1, hi=24, time_limit=900, workers=8)
    rec = {"min_cells": r.size, "status": r.status, "lb_cells": r.bound_lb, "cells_circuit": r.gates, "outputs": r.outputs}
    if r.size:
        for v in COSTS:
            Lv = lib_for(v); best = None
            for m in range(r.size, r.size + 4):
                rr = build(Lv, n_in, tts, m, None, minimize="cost", time_limit=600, workers=8)
                if rr.status in ("OPTIMAL", "FEASIBLE") and (best is None or rr.cost < best.cost): best = rr
            if best:
                assert simulate(Lv, n_in, best.gates, best.outputs) == list(tts)
                rec[v] = {"transistors": best.cost, "cells": best.size, "circuit": best.gates, "outputs": best.outputs}
    rec["wall"] = round(time.time() - t0, 1); out[name] = rec
    print(name, {k: (v if not isinstance(v, dict) else v.get("transistors")) for k, v in rec.items() if k not in ("cells_circuit", "outputs")}, flush=True)
    json.dump(out, open("results/libcost_targets.json", "w"), indent=1)
