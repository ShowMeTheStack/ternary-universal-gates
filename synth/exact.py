#!/usr/bin/env python3
"""Exact synthesis of k-valued circuits from a fixed gate library with CP-SAT.

Model: a circuit is a sequence of 2-input gates g_0..g_{m-1}; gate i chooses a type
from the library, a left operand and a right operand among the n primary inputs and
gates 0..i-1 (DAG model: fan-out is free). Each target output must equal the value of
some input or gate on every row of the truth table. We minimise sum of gate costs
(all 1 = minimum gate count), optionally under a depth bound; or minimise depth.

Values are integers 0..k-1 (for ternary: 0=-,1=0,2=+). A gate table is a flat list
of length k*k indexed by a*k+b (a = left operand value, b = right operand value).

Validated on binary NAND (XOR=4, FA=9) and on the paper's g451 half-adder figures.
"""
from __future__ import annotations
import itertools, time, sys, json
from dataclasses import dataclass, field
from ortools.sat.python import cp_model

@dataclass
class Lib:
    k: int
    tables: list            # list of flat k*k tables
    names: list
    costs: list = None      # per-type cost (default 1 each)
    arity: list = None      # per-type arity: 2 (binary), 1 (unary: ignores right operand), 0 (constant)
    def __post_init__(self):
        if self.costs is None: self.costs = [1]*len(self.tables)
        if self.arity is None: self.arity = [2]*len(self.tables)

@dataclass
class Result:
    status: str
    size: int | None = None
    cost: int | None = None
    depth: int | None = None
    gates: list = field(default_factory=list)   # (type_name, left, right) with operands 'x0','x1',.. or 'g3'
    outputs: list = field(default_factory=list)
    wall: float = 0.0
    bound_lb: int | None = None

def rows(k, n):
    return list(itertools.product(range(k), repeat=n))

def build(lib: Lib, n_in: int, targets: list[list[int]], m: int, max_depth: int | None,
          minimize: str, allow_input_outputs=True, time_limit=60.0, workers=8, hint=None, tree=False):
    """targets: list of truth tables, each a list of length k^n_in in row order of rows(k,n_in)."""
    k, T = lib.k, len(lib.tables)
    R = rows(k, n_in)
    nR = len(R)
    mdl = cp_model.CpModel()
    # gate i: type, left, right (operand index: 0..n_in-1 inputs, n_in+j gate j)
    typ = [mdl.NewIntVar(0, T-1, f"t{i}") for i in range(m)]
    lft = [mdl.NewIntVar(0, n_in+i-1, f"l{i}") for i in range(m)]
    rgt = [mdl.NewIntVar(0, n_in+i-1, f"r{i}") for i in range(m)]
    val = [[mdl.NewIntVar(0, k-1, f"v{i}_{t}") for t in range(nR)] for i in range(m)]
    # stacked library table: index = typ*k*k + a*k + b
    stacked = [v for tab in lib.tables for v in tab]
    for i in range(m):
        for t in range(nR):
            cands = [R[t][j] for j in range(n_in)] + [val[j][t] for j in range(i)]
            lv = mdl.NewIntVar(0, k-1, f"lv{i}_{t}")
            rv = mdl.NewIntVar(0, k-1, f"rv{i}_{t}")
            mdl.AddElement(lft[i], cands, lv)
            mdl.AddElement(rgt[i], cands, rv)
            idx = mdl.NewIntVar(0, T*k*k-1, f"ix{i}_{t}")
            mdl.Add(idx == typ[i]*(k*k) + lv*k + rv)
            mdl.AddElement(idx, stacked, val[i][t])
    # unary cells: right operand := left operand; constants: both operands := input 0
    for i in range(m):
        for t in range(T):
            if lib.arity[t] == 2: continue
            bt = mdl.NewBoolVar(""); mdl.Add(typ[i] == t).OnlyEnforceIf(bt); mdl.Add(typ[i] != t).OnlyEnforceIf(bt.Not())
            if lib.arity[t] == 1:
                mdl.Add(rgt[i] == lft[i]).OnlyEnforceIf(bt)
            else:
                mdl.Add(lft[i] == 0).OnlyEnforceIf(bt); mdl.Add(rgt[i] == 0).OnlyEnforceIf(bt)
    # outputs
    n_nodes = n_in + m
    outs = []
    for o, tgt in enumerate(targets):
        lo = 0 if allow_input_outputs else n_in
        ov = mdl.NewIntVar(lo, n_nodes-1, f"o{o}")
        outs.append(ov)
        for t in range(nR):
            cands = [R[t][j] for j in range(n_in)] + [val[j][t] for j in range(m)]
            mdl.AddElement(ov, cands, tgt[t])
    # every gate is used: by a later gate or as an output (tree model: exactly once)
    for i in range(m):
        uses = []
        for j in range(i+1, m):
            b1 = mdl.NewBoolVar(""); mdl.Add(lft[j] == n_in+i).OnlyEnforceIf(b1); mdl.Add(lft[j] != n_in+i).OnlyEnforceIf(b1.Not()); uses.append(b1)
            b2 = mdl.NewBoolVar(""); mdl.Add(rgt[j] == n_in+i).OnlyEnforceIf(b2); mdl.Add(rgt[j] != n_in+i).OnlyEnforceIf(b2.Not()); uses.append(b2)
        for ov in outs:
            b3 = mdl.NewBoolVar(""); mdl.Add(ov == n_in+i).OnlyEnforceIf(b3); mdl.Add(ov != n_in+i).OnlyEnforceIf(b3.Not()); uses.append(b3)
        if tree:
            mdl.AddExactlyOne(uses)   # fan-out 1: formula (tree) model
        else:
            mdl.AddBoolOr(uses)
    # no two gates identical (same type and operands)
    key = [mdl.NewIntVar(0, T*n_nodes*n_nodes, f"key{i}") for i in range(m)]
    for i in range(m):
        mdl.Add(key[i] == typ[i]*(n_nodes*n_nodes) + lft[i]*n_nodes + rgt[i])
    if not tree:
        mdl.AddAllDifferent(key)   # DAG model: identical gates would be shared
    # symmetry breaking: if gate i+1 does not use gate i, then key[i] <(=) key[i+1]
    for i in range(m-1):
        uses_prev = mdl.NewBoolVar("")
        b1 = mdl.NewBoolVar(""); mdl.Add(lft[i+1] == n_in+i).OnlyEnforceIf(b1); mdl.Add(lft[i+1] != n_in+i).OnlyEnforceIf(b1.Not())
        b2 = mdl.NewBoolVar(""); mdl.Add(rgt[i+1] == n_in+i).OnlyEnforceIf(b2); mdl.Add(rgt[i+1] != n_in+i).OnlyEnforceIf(b2.Not())
        mdl.AddBoolOr([b1, b2]).OnlyEnforceIf(uses_prev)
        mdl.AddBoolAnd([b1.Not(), b2.Not()]).OnlyEnforceIf(uses_prev.Not())
        (mdl.Add(key[i] <= key[i+1]) if tree else mdl.Add(key[i] < key[i+1])).OnlyEnforceIf(uses_prev.Not())
    # depth
    dep = None
    if max_depth is not None or minimize == "depth":
        D = max_depth if max_depth is not None else m
        dep = [mdl.NewIntVar(1, D, f"d{i}") for i in range(m)]
        for i in range(m):
            for j in range(i):
                bl = mdl.NewBoolVar(""); mdl.Add(lft[i] == n_in+j).OnlyEnforceIf(bl); mdl.Add(lft[i] != n_in+j).OnlyEnforceIf(bl.Not())
                mdl.Add(dep[i] >= dep[j] + 1).OnlyEnforceIf(bl)
                br = mdl.NewBoolVar(""); mdl.Add(rgt[i] == n_in+j).OnlyEnforceIf(br); mdl.Add(rgt[i] != n_in+j).OnlyEnforceIf(br.Not())
                mdl.Add(dep[i] >= dep[j] + 1).OnlyEnforceIf(br)
        if minimize == "depth":
            dmax = mdl.NewIntVar(0, D, "dmax")
            for i in range(m): mdl.Add(dmax >= dep[i])
            mdl.Minimize(dmax)
    if minimize == "cost":
        mdl.Minimize(sum(mdl_cost(mdl, typ[i], lib.costs) for i in range(m)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    t0 = time.time()
    st = solver.Solve(mdl)
    wall = time.time() - t0
    name = solver.StatusName(st)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        def nm(idx): return f"x{idx}" if idx < n_in else f"g{idx-n_in}"
        gates = [(lib.names[solver.Value(typ[i])], nm(solver.Value(lft[i])), nm(solver.Value(rgt[i]))) for i in range(m)]
        outputs = [nm(solver.Value(o)) for o in outs]
        depth = max(solver.Value(d) for d in dep) if dep else None
        cost = sum(lib.costs[solver.Value(typ[i])] for i in range(m))
        return Result(name, m, cost, depth, gates, outputs, wall)
    return Result(name, wall=wall)

def mdl_cost(mdl, tvar, costs):
    if len(set(costs)) == 1: return costs[0]
    c = mdl.NewIntVar(min(costs), max(costs), "")
    mdl.AddElement(tvar, costs, c)
    return c

def min_size(lib, n_in, targets, lo=1, hi=30, max_depth=None, time_limit=60.0, workers=8, verbose=False, tree=False):
    """Smallest m such that a circuit with m gates exists (DAG model). Returns Result (status
    'OPTIMAL' if proven, 'UNKNOWN' with bound_lb if time limits hit)."""
    lb = lo
    for m in range(lo, hi+1):
        r = build(lib, n_in, targets, m, max_depth, minimize="none", time_limit=time_limit, workers=workers, tree=tree)
        if verbose: print(f"  m={m}: {r.status} ({r.wall:.1f}s)", file=sys.stderr)
        if r.status in ("OPTIMAL", "FEASIBLE"):
            r.status = "OPTIMAL" if lb == m else "FEASIBLE_LB_UNPROVEN"
            r.bound_lb = lb
            return r
        if r.status == "INFEASIBLE":
            lb = m + 1
        else:  # UNKNOWN: can't tighten lb
            pass
    return Result("UNKNOWN", bound_lb=lb)

def min_depth(lib, n_in, targets, size_cap, time_limit=60.0, workers=8, tree=False):
    """Smallest depth D for which some circuit of at most size_cap gates exists."""
    for D in range(1, size_cap+1):
        for m in range(D, size_cap+1):
            r = build(lib, n_in, targets, m, max_depth=D, minimize="none", time_limit=time_limit, workers=workers, tree=tree)
            if r.status in ("OPTIMAL", "FEASIBLE"):
                r.status = "OPTIMAL"; return r
            if r.status != "INFEASIBLE":
                return Result("UNKNOWN")
    return Result("INFEASIBLE")

# ------------------------------------------------------------------ targets
def ternary_targets():
    k = 3
    def hs(x, y):
        s = (x-1)+(y-1); s = s-3 if s > 1 else s+3 if s < -1 else s; return s+1
    def hc(x, y):
        s = (x-1)+(y-1); return 2 if s == 2 else 0 if s == -2 else 1
    def fs(a, b, c):
        s = (a-1)+(b-1)+(c-1); return (s + 1) % 3            # index of balanced digit d = ((s+1) mod 3) - 1
    def fc(a, b, c):
        s = (a-1)+(b-1)+(c-1); d = ((s + 1) % 3) - 1; return (s - d)//3 + 1
    def mul(x, y): return (x-1)*(y-1)+1
    R2, R3 = rows(k, 2), rows(k, 3)
    return {
        "h_sum":   (2, [hs(*r) for r in R2]),
        "h_carry": (2, [hc(*r) for r in R2]),
        "fa_sum":  (3, [fs(*r) for r in R3]),
        "fa_carry":(3, [fc(*r) for r in R3]),
        "mul":     (2, [mul(*r) for r in R2]),
    }

def gate_table_from_label(label, k=3):
    t = []
    for _ in range(k*k):
        t.append(label % k); label //= k
    # paper convention: entry i = 3*x + y  (x = left/row, y = right/col)  -> matches a*k+b
    return t

if __name__ == "__main__":
    # --- self tests
    nand = Lib(2, [[1,1,1,0]], ["NAND"])
    xor = [0,1,1,0]; and_ = [0,0,0,1]
    r = min_size(nand, 2, [xor]); print("NAND XOR:", r.status, r.size, r.gates, f"{r.wall:.1f}s"); assert r.size == 4
    r = min_size(nand, 2, [and_]); print("NAND AND:", r.status, r.size); assert r.size == 2
    R3 = rows(2, 3)
    fa_s = [(a+b+c) % 2 for a,b,c in R3]; fa_c = [(a+b+c)//2 for a,b,c in R3]
    r = min_size(nand, 3, [fa_s, fa_c], lo=6, time_limit=120); print("NAND FA (joint):", r.status, r.size, r.depth, r.gates, f"{r.wall:.1f}s"); assert r.size == 9
    T = ternary_targets()
    g451 = Lib(3, [gate_table_from_label(451)], ["g451"])
    r = min_size(g451, 2, [T["h_sum"][1]]); print("g451 h_sum DAG:", r.status, r.size, r.gates, f"{r.wall:.1f}s")
    r = min_size(g451, 2, [T["h_carry"][1]]); print("g451 h_carry DAG:", r.status, r.size, r.gates, f"{r.wall:.1f}s")
    r = min_depth(g451, 2, [T["h_sum"][1]], size_cap=8); print("g451 h_sum min depth:", r.status, r.depth, r.size)
    r = min_size(g451, 2, [T["h_sum"][1], T["h_carry"][1]]); print("g451 HA joint DAG:", r.status, r.size, r.depth, r.gates, f"{r.wall:.1f}s")
    print("fa_sum table:", T["fa_sum"][1]); print("fa_carry table:", T["fa_carry"][1])


def bounded_search(lib, n_in, targets, ub, time_limit_lb=60.0, time_limit_ub=300.0, workers=8,
                   lb_start=1, verbose=False):
    """Two-phase search for hard instances. Upward phase: prove infeasibility for
    m = lb_start.. until a proof times out or a circuit is found (gives LB). Downward
    phase: starting from the known upper bound `ub`, try m = ub-1, ub-2, ... until a
    solve fails to find a circuit within time_limit_ub (gives UB). Returns dict with
    lb, ub, status ('OPTIMAL' iff lb == ub), best circuit."""
    lb, best = lb_start, None
    m = lb_start
    while m < ub:
        r = build(lib, n_in, targets, m, None, minimize="none", time_limit=time_limit_lb, workers=workers)
        if verbose: print(f"  up m={m}: {r.status} ({r.wall:.1f}s)", file=sys.stderr)
        if r.status == "INFEASIBLE":
            lb = m + 1; m += 1; continue
        if r.status in ("OPTIMAL", "FEASIBLE"):
            best = r; ub = m; break
        break  # UNKNOWN: lb stays
    # downward from ub
    m = ub - 1
    while m >= lb:
        r = build(lib, n_in, targets, m, None, minimize="none", time_limit=time_limit_ub, workers=workers)
        if verbose: print(f"  down m={m}: {r.status} ({r.wall:.1f}s)", file=sys.stderr)
        if r.status in ("OPTIMAL", "FEASIBLE"):
            best = r; ub = m; m -= 1; continue
        if r.status == "INFEASIBLE":
            lb = m + 1
        break
    return {"lb": lb, "ub": ub, "status": "OPTIMAL" if lb == ub else "BOUNDS",
            "gates": best.gates if best else None, "outputs": best.outputs if best else None,
            "depth_of_ub": best.depth if best else None}


# ------------------------------------------------------------------ circuits as data
# A circuit is (gates, outputs): gates = [(type_name, left, right), ...] with operand names
# 'x<i>' (primary input) or 'g<j>' (earlier gate); outputs = [name, ...].

def simulate(lib, n_in, gates, outputs):
    """Return the truth tables (lists over rows(k,n_in)) of the given outputs."""
    k = lib.k
    tabs = {lib.names[i]: lib.tables[i] for i in range(len(lib.tables))}
    R = rows(k, n_in)
    vals = {}
    for i in range(n_in):
        vals[f"x{i}"] = [r[i] for r in R]
    for j, (tn, l, r) in enumerate(gates):
        tab = tabs[tn]
        vals[f"g{j}"] = [tab[a * k + b] for a, b in zip(vals[l], vals[r])]
    return [vals[o] for o in outputs]

def instantiate(gates, outputs, in_names, acc):
    """Append a copy of circuit (gates, outputs) to gate list `acc`, with its primary inputs
    renamed to in_names. Returns the list of output names in the enlarged circuit."""
    base = len(acc)
    ren = {f"x{i}": nm for i, nm in enumerate(in_names)}
    for j, (tn, l, r) in enumerate(gates):
        ren[f"g{j}"] = f"g{base + j}"
        acc.append((tn, ren[l], ren[r]))
    return [ren[o] for o in outputs]

def dedupe(gates, outputs):
    """Merge structurally identical gates (same type and operands) — exact DAG sharing."""
    seen, ren, out = {}, {}, []
    for j, (tn, l, r) in enumerate(gates):
        key = (tn, ren.get(l, l), ren.get(r, r))
        if key in seen:
            ren[f"g{j}"] = seen[key]
        else:
            seen[key] = f"g{len(out)}"; ren[f"g{j}"] = seen[key]; out.append(key)
    return out, [ren.get(o, o) for o in outputs]

def prune(gates, outputs):
    """Drop gates not reachable from the outputs; renumber."""
    need, stack = set(), [o for o in outputs if o.startswith("g")]
    while stack:
        g = stack.pop()
        if g in need: continue
        need.add(g)
        _, l, r = gates[int(g[1:])]
        stack += [x for x in (l, r) if x.startswith("g")]
    keep = sorted(need, key=lambda s: int(s[1:]))
    ren = {g: f"g{i}" for i, g in enumerate(keep)}
    new = [(gates[int(g[1:])][0], ren.get(gates[int(g[1:])][1], gates[int(g[1:])][1]), ren.get(gates[int(g[1:])][2], gates[int(g[1:])][2])) for g in keep]
    return new, [ren.get(o, o) for o in outputs]

def chained_fa(hs, hc, which="joint"):
    """Chained-half-adder full adder from HA circuits hs=(gates,outs) for h_sum, hc for h_carry.
    Inputs a=x0, b=x1, c=x2. which in {'sum','carry','joint'}. Returns (gates, outputs)."""
    acc = []
    s1 = instantiate(*hs, ["x0", "x1"], acc)[0]
    c1 = instantiate(*hc, ["x0", "x1"], acc)[0]
    s2 = instantiate(*hs, [s1, "x2"], acc)[0]
    c2 = instantiate(*hc, [s1, "x2"], acc)[0]
    co = instantiate(*hs, [c1, c2], acc)[0]
    outs = {"sum": [s2], "carry": [co], "joint": [s2, co]}[which]
    return prune(*dedupe(acc, outs))

def improve_ub(lib, n_in, targets, hint, time_limit=300.0, workers=8):
    """Fixed-size model with per-gate 'active' booleans, hinted with a known circuit;
    minimises the number of active gates. hint = (gates, outputs). Returns Result with the
    compacted circuit, or the hint itself if nothing better is found."""
    hg, ho = hint
    m = len(hg)
    k, T = lib.k, len(lib.tables)
    R = rows(k, n_in); nR = len(R)
    tidx = {n: i for i, n in enumerate(lib.names)}
    mdl = cp_model.CpModel()
    act = [mdl.NewBoolVar(f"a{i}") for i in range(m)]
    typ = [mdl.NewIntVar(0, T-1, f"t{i}") for i in range(m)]
    lft = [mdl.NewIntVar(0, n_in+i-1, f"l{i}") for i in range(m)]
    rgt = [mdl.NewIntVar(0, n_in+i-1, f"r{i}") for i in range(m)]
    val = [[mdl.NewIntVar(0, k-1, f"v{i}_{t}") for t in range(nR)] for i in range(m)]
    stacked = [v for tab in lib.tables for v in tab]
    for i in range(m):
        for t in range(nR):
            cands = [R[t][j] for j in range(n_in)] + [val[j][t] for j in range(i)]
            lv = mdl.NewIntVar(0, k-1, ""); rv = mdl.NewIntVar(0, k-1, "")
            mdl.AddElement(lft[i], cands, lv); mdl.AddElement(rgt[i], cands, rv)
            idx = mdl.NewIntVar(0, T*k*k-1, "")
            mdl.Add(idx == typ[i]*(k*k) + lv*k + rv)
            mdl.AddElement(idx, stacked, val[i][t])
    # an active gate may only reference active gates
    ref = {}  # (i, j) -> bool "gate i references gate j"
    for i in range(m):
        for j in range(i):
            b = mdl.NewBoolVar("")
            bl = mdl.NewBoolVar(""); mdl.Add(lft[i] == n_in+j).OnlyEnforceIf(bl); mdl.Add(lft[i] != n_in+j).OnlyEnforceIf(bl.Not())
            br = mdl.NewBoolVar(""); mdl.Add(rgt[i] == n_in+j).OnlyEnforceIf(br); mdl.Add(rgt[i] != n_in+j).OnlyEnforceIf(br.Not())
            mdl.AddBoolOr([bl, br]).OnlyEnforceIf(b); mdl.AddBoolAnd([bl.Not(), br.Not()]).OnlyEnforceIf(b.Not())
            mdl.AddImplication(b, act[j]).OnlyEnforceIf(act[i])
            ref[(i, j)] = b
    n_nodes = n_in + m
    outs, oref = [], {}
    for o, tgt in enumerate(targets):
        ov = mdl.NewIntVar(0, n_nodes-1, f"o{o}"); outs.append(ov)
        for t in range(nR):
            cands = [R[t][j] for j in range(n_in)] + [val[j][t] for j in range(m)]
            mdl.AddElement(ov, cands, tgt[t])
        for j in range(m):
            b = mdl.NewBoolVar(""); mdl.Add(ov == n_in+j).OnlyEnforceIf(b); mdl.Add(ov != n_in+j).OnlyEnforceIf(b.Not())
            mdl.AddImplication(b, act[j]); oref[(o, j)] = b
    # active gates must be used by an active gate or an output
    for j in range(m):
        users = [oref[(o, j)] for o in range(len(targets))]
        for i in range(j+1, m):
            u = mdl.NewBoolVar(""); mdl.AddBoolAnd([ref[(i, j)], act[i]]).OnlyEnforceIf(u); mdl.AddBoolOr([ref[(i, j)].Not(), act[i].Not()]).OnlyEnforceIf(u.Not())
            users.append(u)
        mdl.AddBoolOr(users).OnlyEnforceIf(act[j])
    mdl.Minimize(sum(act))
    # hint
    def idx_of(nm): return int(nm[1:]) if nm[0] == "x" else n_in + int(nm[1:])
    for i, (tn, l, r) in enumerate(hg):
        mdl.AddHint(act[i], 1); mdl.AddHint(typ[i], tidx[tn]); mdl.AddHint(lft[i], idx_of(l)); mdl.AddHint(rgt[i], idx_of(r))
    for o, nm in enumerate(ho):
        mdl.AddHint(outs[o], idx_of(nm))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    t0 = time.time(); st = solver.Solve(mdl); wall = time.time() - t0
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        def nm(i): return f"x{i}" if i < n_in else f"g{i-n_in}"
        gates = [(lib.names[solver.Value(typ[i])], nm(solver.Value(lft[i])), nm(solver.Value(rgt[i]))) for i in range(m)]
        outputs = [nm(solver.Value(o)) for o in outs]
        g2, o2 = prune(gates, outputs)
        assert simulate(lib, n_in, g2, o2) == list(targets), "improve_ub produced a wrong circuit"
        return Result(solver.StatusName(st) + ("_PROVEN" if st == cp_model.OPTIMAL else ""), len(g2), len(g2), None, g2, o2, wall)
    return Result("HINT_ONLY", len(hg), len(hg), None, hg, ho, wall)


def chained_fa_from_joint(hj, hs, hc, which="joint"):
    """Chained full adder built from a JOINT half-adder circuit hj=(gates,[sum,carry])
    (shared logic) where useful: HA1 = joint(a,b) -> (s1,c1); HA2 = joint(s1,c) -> (s2,c2)
    (or carry-only / sum-only when that is all that is needed); c_out = h_sum(c1,c2)."""
    acc = []
    s1, c1 = instantiate(*hj, ["x0", "x1"], acc)
    if which == "sum":
        s2 = instantiate(*hs, [s1, "x2"], acc)[0]; outs = [s2]
    elif which == "carry":
        c2 = instantiate(*hc, [s1, "x2"], acc)[0]
        co = instantiate(*hs, [c1, c2], acc)[0]; outs = [co]
    else:
        s2, c2 = instantiate(*hj, [s1, "x2"], acc)
        co = instantiate(*hs, [c1, c2], acc)[0]; outs = [s2, co]
    return prune(*dedupe(acc, outs))
