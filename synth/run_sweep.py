#!/usr/bin/env python3
"""Resumable sweep: exact synthesis of arithmetic targets for every universal gate.

One JSON result file per (gate, task) under results/<task>/<gate>.json; a task for a gate
is skipped when its file exists, so the sweep can be killed/rebooted and re-run.
Parallelism: a process pool over gates; each CP-SAT solve uses `--solver-workers` threads.

Tasks:
  ha_sum, ha_carry        2-input, min size (DAG) + min depth
  ha_joint                2-input, 2 outputs sharing logic, min size
  fa_sum, fa_carry        3-input (27 rows), min size, min depth
  fa_joint                3-input, 2 outputs, min size
  mul                     2-input balanced product, min size

Usage: run_sweep.py --enum results/enumerate.csv --out results --tasks fa_joint,fa_sum,... \
                    [--gates 451,1391] [--procs 16] [--solver-workers 2] [--time-limit 600]
"""
import argparse, csv, json, os, sys, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exact import Lib, min_size, min_depth, build, bounded_search, improve_ub, chained_fa, chained_fa_from_joint, simulate, ternary_targets, gate_table_from_label

T = ternary_targets()
TASKS = {
    "ha_sum":   (2, [T["h_sum"][1]],   1, 10),
    "ha_carry": (2, [T["h_carry"][1]], 1, 10),
    "ha_joint": (2, [T["h_sum"][1], T["h_carry"][1]], 2, 16),
    "fa_sum":   (3, [T["fa_sum"][1]],  3, 24),
    "fa_carry": (3, [T["fa_carry"][1]],3, 24),
    "fa_joint": (3, [T["fa_sum"][1], T["fa_carry"][1]], 5, 32),
    "mul":      (2, [T["mul"][1]],     1, 12),
}

def universal_gates(enum_csv):
    out = []
    with open(enum_csv, newline="") as f:
        for r in csv.DictReader(f):
            if r["closure_size"] == "19683":
                out.append((int(r["gate"]), int(r["canon4"])))
    return out

def solve_one(args):
    try:
        return _solve_one(args)
    except Exception as e:   # record the failure, keep the pool alive
        gate, task, outdir = args[0], args[1], args[2]
        path = os.path.join(outdir, task, f"{gate}.json")
        rec = {"gate": gate, "task": task, "status": "ERROR", "error": repr(e)[:300]}
        tmp = path + ".tmp"; json.dump(rec, open(tmp, "w")); os.replace(tmp, path)
        return gate, task, "ERROR"

def _solve_one(args):
    gate, task, outdir, time_limit, workers, do_depth = args
    path = os.path.join(outdir, task, f"{gate}.json")
    if os.path.exists(path):
        try:
            json.load(open(path)); return gate, task, "skip"
        except Exception:
            os.replace(path, path + ".corrupt")   # e.g. zero-length file left by a power loss
    n_in, targets, lo, hi = TASKS[task]
    lib = Lib(3, [gate_table_from_label(gate)], [f"g{gate}"])
    t0 = time.time()
    if task.startswith("fa_"):
        # 27-row single-gate instances: verified chained-HA circuit as UB, hinted CP-SAT
        # improvement of the UB, and upward infeasibility proofs for the LB.
        def ha_circuit(name, tt):
            """exact Stage A circuit from disk if it exists and verifies; else solve (short budget)."""
            p = os.path.join(outdir, name, f"{gate}.json")
            if os.path.exists(p):
                try:
                    d = json.load(open(p))
                    if d.get("gates") and d.get("outputs"):
                        c = ([tuple(g) for g in d["gates"]], list(d["outputs"]))
                        if simulate(lib, 2, *c) == [tt]: return c, len(c[0])
                except Exception:
                    pass
            r = min_size(lib, 2, [tt], lo=1, hi=12, time_limit=60, workers=workers)
            return ((r.gates, r.outputs), r.size) if r.size else (None, None)
        (hsc, gs_), (hcc, gc_) = ha_circuit("ha_sum", T["h_sum"][1]), ha_circuit("ha_carry", T["h_carry"][1])
        class _R: pass
        hs, hc = _R(), _R(); hs.size, hc.size = gs_, gc_
        which = {"fa_sum": "sum", "fa_carry": "carry", "fa_joint": "joint"}[task]
        cands = [chained_fa(hsc, hcc, which)] if (hsc and hcc) else []
        jp = os.path.join(outdir, "ha_joint", f"{gate}.json")   # reuse the exact joint HA circuit if available
        if os.path.exists(jp):
            try:
                hj = json.load(open(jp))
                if hj.get("gates") and hj.get("outputs") and len(hj["outputs"]) == 2:
                    hjc = ([tuple(g) for g in hj["gates"]], list(hj["outputs"]))
                    if simulate(lib, 2, *hjc) == [T["h_sum"][1], T["h_carry"][1]]:
                        if hsc and hcc: cands.append(chained_fa_from_joint(hjc, hsc, hcc, which))
            except Exception:
                pass
        cands = [c for c in cands if simulate(lib, 3, *c) == list(targets)]
        if cands:
            cg, co = min(cands, key=lambda c: len(c[0]))
            ub0 = len(cg)
            imp = improve_ub(lib, n_in, targets, (cg, co), time_limit=time_limit, workers=workers)
            ub, gates, outs = imp.size, imp.gates, imp.outputs
        else:   # no half-adder circuits available (sum needs > 12 gates): lower bound only
            ub0, ub, gates, outs = None, hi, None, None
            imp = type("I", (), {"status": "NO_UB"})()
        lb, m = lo, lo
        while m < ub:
            r0 = build(lib, n_in, targets, m, None, minimize="none", time_limit=min(90, time_limit), workers=workers)
            if r0.status == "INFEASIBLE":
                lb = m + 1; m += 1; continue
            if r0.status in ("OPTIMAL", "FEASIBLE"):
                ub, gates, outs = m, r0.gates, r0.outputs
            break
        status = "OPTIMAL" if lb == ub else "BOUNDS"
        rec = {"gate": gate, "task": task, "status": status, "size": ub, "lb": lb, "ub": ub,
               "ub_chained": ub0, "ub_improved_status": imp.status, "Gs": hs.size, "Gc": hc.size,
               "gates": gates, "outputs": outs, "wall_size": round(time.time() - t0, 2), "time_limit": time_limit}
        r = type("R", (), {"size": ub if status == "OPTIMAL" else None})()
    else:
        r = min_size(lib, n_in, targets, lo=lo, hi=hi, time_limit=time_limit, workers=workers)
        rec = {"gate": gate, "task": task, "status": r.status, "size": r.size, "lb": r.bound_lb,
               "depth_of_size_opt": r.depth, "gates": r.gates, "outputs": r.outputs,
               "wall_size": round(time.time() - t0, 2), "time_limit": time_limit}
    if do_depth and r.size is not None:
        t1 = time.time()
        d = min_depth(lib, n_in, targets, size_cap=min(hi, r.size + 6), time_limit=time_limit, workers=workers)
        rec.update({"min_depth": d.depth, "min_depth_status": d.status, "min_depth_size": d.size,
                    "min_depth_gates": d.gates, "wall_depth": round(time.time() - t1, 2)})
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f)
    os.replace(tmp, path)
    return gate, task, rec["status"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enum", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--tasks", default="fa_joint")
    ap.add_argument("--gates", default=None, help="comma list; default: all universal gates")
    ap.add_argument("--reps4", action="store_true", help="one gate per Z2xZ2 class only")
    ap.add_argument("--procs", type=int, default=max(1, mp.cpu_count() // 2))
    ap.add_argument("--solver-workers", type=int, default=2)
    ap.add_argument("--time-limit", type=float, default=600)
    ap.add_argument("--depth", action="store_true", help="also compute min depth")
    ap.add_argument("--redo-unknown", action="store_true", help="recompute records whose status is UNKNOWN/BOUNDS")
    a = ap.parse_args()
    gates = universal_gates(a.enum)
    if a.reps4:
        seen, reps = set(), []
        for g, c4 in gates:
            if c4 not in seen:
                seen.add(c4); reps.append((g, c4))
        gates = reps
    if a.gates:
        want = {int(x) for x in a.gates.split(",")}
        gates = [(g, c) for g, c in gates if g in want]
    tasks = a.tasks.split(",")
    for t in tasks:
        os.makedirs(os.path.join(a.out, t), exist_ok=True)
    jobs = [(g, t, a.out, a.time_limit, a.solver_workers, a.depth) for t in tasks for g, _ in gates]
    def done_ok(j):
        p = os.path.join(a.out, j[1], f"{j[0]}.json")
        if not os.path.exists(p): return False
        if a.redo_unknown:
            try: st = json.load(open(p)).get("status", "")
            except Exception: return False
            if st in ("UNKNOWN", "BOUNDS", "FEASIBLE_LB_UNPROVEN"):
                os.replace(p, p + ".v1"); return False
        return True
    todo = [j for j in jobs if not done_ok(j)]
    print(f"{len(jobs)} jobs, {len(todo)} to do, {a.procs} procs x {a.solver_workers} solver threads", flush=True)
    t0 = time.time(); done = 0
    with mp.Pool(a.procs) as pool:
        for gate, task, st in pool.imap_unordered(solve_one, todo, chunksize=1):
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"[{time.time()-t0:7.0f}s] {done}/{len(todo)}  last: g{gate} {task} {st}", flush=True)

if __name__ == "__main__":
    main()
