#!/usr/bin/env python3
"""Recompute every number quoted in the paper from the raw result files in results/."""
import csv, json, glob, os, sys, statistics, collections
R = sys.argv[1] if len(sys.argv) > 1 else "results"
C = collections.Counter
def dist(c): return "{" + ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda kv: (kv[0] is None, kv[0]))) + "}"
def I(s): return int(s) if s not in ("", None) else None
def med(xs): return statistics.median(xs)
def spearman(x, y):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v); i = 0
        while i < len(v):
            j = i
            while j+1 < len(v) and v[s[j+1]] == v[s[i]]: j += 1
            for k in range(i, j+1): r[s[k]] = (i+j)/2+1
            i = j+1
        return r
    rx, ry = rank(x), rank(y); n = len(x); mx, my = sum(rx)/n, sum(ry)/n
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry)); den = (sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den
sm = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_summary.csv"))}
ha = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_ha.csv"))}
reps4 = sorted({int(r["canon4"]) for r in sm.values()}); assert len(reps4) == 966
members4 = collections.defaultdict(list)
for g, r in sm.items(): members4[int(r["canon4"])].append(g)
print("== class invariance: metric vectors mixed within classes")
for key, n in (("canon12", 322), ("canon4", 966)):
    for label, fn in (("depths", lambda g: (ha[g]["Ds"], ha[g]["Dc"])), ("depths+sizes", lambda g: (ha[g]["Ds"], ha[g]["Dc"], sm[g]["ha_sum_size"], sm[g]["ha_carry_size"]))):
        by = collections.defaultdict(set)
        for g in sm: by[sm[g][key]].add(fn(g))
        print(f"  {key} ({len(by)} classes) {label}: mixed in {sum(len(v)>1 for v in by.values())}  (unproven sums, all >= 11, count as a distinct value)")
# with joint & mul sizes from summary
by = collections.defaultdict(set)
for g, r in sm.items(): by[r["canon12"]].add((ha[g]["Ds"], ha[g]["Dc"], r["ha_sum_size"], r["ha_carry_size"], r["ha_joint_size"], r["mul_size"]))
print("  canon12 all six metrics mixed in", sum(len(v)>1 for v in by.values()))

print("== library cost (libcost/*.json), 966 class representatives")
lc = {}
for f in glob.glob(f"{R}/libcost/*.json"):
    d = json.load(open(f)); lc[d["gate"]] = d
print("  files:", len(lc), "all reps covered:", all(g in lc for g in reps4))
cells = C(d["min_cells"] for d in lc.values()); st = C(d["min_cells_status"] for d in lc.values())
print("  min_cells status", dict(st), "dist", dist(cells))
cost = {g: d["costs"]["lin2011"]["transistors"] for g, d in lc.items()}
cs = sorted(cost.values())
print("  lin2011: min", cs[0], "max", cs[-1], "median", med(cs), "Q1/Q3", cs[len(cs)//4], cs[3*len(cs)//4], ">42:", sum(c > 42 for c in cs), ">72:", sum(c > 72 for c in cs))
print("  cheapest gates:", sorted((c, g, lc[g]["min_cells"]) for g, c in cost.items() if c <= 26))
for v in ("sharifi2015", "younepal2011"):
    cv = {g: d["costs"][v]["transistors"] for g, d in lc.items()}
    print(f"  {v}: median", med(cv.values()), "min", min(cv.values()), "max", max(cv.values()), "spearman vs lin2011", round(spearman([cost[g] for g in reps4], [cv[g] for g in reps4]), 3))
cv1 = {g: d["costs"]["sharifi2015"]["transistors"] for g, d in lc.items()}; cv2 = {g: d["costs"]["younepal2011"]["transistors"] for g, d in lc.items()}
print("  spearman sharifi vs younepal", round(spearman([cv1[g] for g in reps4], [cv2[g] for g in reps4]), 3))
cells_cost_hist = C((d["min_cells"], d["costs"]["lin2011"]["transistors"]) for d in lc.values())
for g in (8431, 4066, 3394, 6640, 451, 1894, 1426, 41, 2608, 3416, 1156, 2716, 3575, 7471, 281, 223, 5791, 7033, 1157):
    c4 = int(sm[g]["canon4"]); d = lc.get(c4)
    print(f"  g{g} canon4={c4} canon12={sm[g]['canon12']} cells={d['min_cells']} ({d['min_cells_status']}, lb {d['lb_cells']}) lin={d['costs']['lin2011']['transistors']} sharifi={d['costs']['sharifi2015']['transistors']} younepal={d['costs']['younepal2011']['transistors']}")
print("== library optima of targets (libcost_targets.json)")
T = json.load(open(f"{R}/libcost_targets.json"))
for k, v in T.items():
    print(f"  {k}: cells {v.get('min_cells')} {v.get('status')} lb {v.get('lb_cells')}", {vk: (vv.get("transistors"), vv.get("cells")) for vk, vv in v.get("costs", {}).items()}, "circuit:", v.get("cells_circuit"))
print("== full adder (synth/fa_carry, fa_joint) per class rep")
fc = {}; fj = {}
for g in reps4:
    fc[g] = json.load(open(f"{R}/synth/fa_carry/{g}.json")); fj[g] = json.load(open(f"{R}/synth/fa_joint/{g}.json"))
print("  fa_carry status", dict(C(d["status"] for d in fc.values())), "optimal:", [(g, d["size"]) for g, d in fc.items() if d["status"] == "OPTIMAL"])
nb = [d for d in fc.values() if d["status"] != "OPTIMAL"]
print("  carry LB dist (non-optimal)", dist(C(d["lb"] for d in nb)), "UB min/max/median", min(d["ub"] for d in nb), max(d["ub"] for d in nb), med([d["ub"] for d in nb]), "UB median all", med([d["ub"] for d in fc.values()]))
print("  carry UB dist", dist(C(d["ub"] for d in fc.values())))
print("  carry: keys", list(fc[reps4[0]].keys()))
# chained carry bound S_joint + S_c + S_s over the 896 classes with proven S_s and a known joint circuit
imp = []; nkn = 0
for g in reps4:
    r = sm[g]
    if r["ha_sum_status"] == "OPTIMAL" and r["ha_joint_size"]:
        nkn += 1; ch = int(r["ha_joint_size"]) + int(r["ha_carry_size"]) + int(r["ha_sum_size"])
        if fc[g]["ub"] < ch: imp.append((ch - fc[g]["ub"], g, ch, fc[g]["ub"]))
print(f"  carry: classes with known chained carry bound {nkn}; solver UB below it in {len(imp)}; max improvement {max(imp)}; ub_chained field vs mine for g1894: {fc[1894].get('ub_chained')}")
imp2 = [(d.get("ub_chained", 0) - d["ub"], g) for g, d in fc.items() if d.get("ub_chained") and d["ub"] < d["ub_chained"]]
print(f"  carry: using the file's own ub_chained: improved in {len(imp2)} classes, max {max(imp2)}; ub_chained present in {sum(1 for d in fc.values() if d.get('ub_chained'))}")
print("  fa_joint status", dict(C(d["status"] for d in fj.values())))
print("  joint LB dist", dist(C(d["lb"] for d in fj.values())), "UB min/max/median", min(d["ub"] for d in fj.values()), max(d["ub"] for d in fj.values()), med([d["ub"] for d in fj.values()]))
print("  joint UB (solver) dist", dist(C(d["ub"] for d in fj.values())))
eq = beat = short = 0; shortfall = 0; shortlist = []; beaters = []; n896 = 0; best = {}
for g in reps4:
    r = sm[g]; ub = fj[g]["ub"]; best[g] = ub
    if r["ha_sum_status"] == "OPTIMAL" and r["ha_joint_status"] == "OPTIMAL":
        n896 += 1; ch = 2*int(r["ha_joint_size"]) + int(r["ha_sum_size"])
        if ub == ch: eq += 1
        elif ub < ch: beat += 1; beaters.append((g, ub, ch))
        else: short += 1; shortfall += ub - ch; shortlist.append(ub - ch); best[g] = ch
print(f"  two-output (rep joint PROVEN): known chained {n896}: equal {eq}, beat {beat} {beaters}, short {short} (total {shortfall}, range {shortlist and (min(shortlist), max(shortlist))})")
eqB = beatB = shortB = 0; shortfallB = 0; shortlistB = []; nB = 0; bestB = {}
for g in reps4:
    r = sm[g]; ub = fj[g]["ub"]; bestB[g] = ub
    if r["ha_sum_status"] == "OPTIMAL" and r["ha_joint_size"]:
        nB += 1; ch = 2*int(r["ha_joint_size"]) + int(r["ha_sum_size"])
        if ub == ch: eqB += 1
        elif ub < ch: beatB += 1
        else: shortB += 1; shortfallB += ub - ch; shortlistB.append(ub - ch); bestB[g] = ch
print(f"  two-output (rep joint ANY known circuit): known {nB}: equal {eqB}, beat {beatB}, short {shortB} (total {shortfallB}, range {shortlistB and (min(shortlistB), max(shortlistB))})")
print("  bestB UB dist", dist(C(bestB.values())), "median", med(bestB.values()))
print("  rep joint status dist", dict(C(sm[g]["ha_joint_status"] for g in reps4)), "rep sum status", dict(C(sm[g]["ha_sum_status"] for g in reps4)))
best = bestB
print("  best-known UB dist (min of solver, chained)", dist(C(best.values())), "median", med(best.values()))
print("  smallest:", sorted((u, g, fj[g]["lb"]) for g, u in best.items())[:10])
print("  tab:fa rows: gate c(G) Ds Dc Ss Sc Sjoint | carry LB UB | FA LB UB chained")
for g in (6640, 8431, 3394, 2608, 3416, 1156, 2716, 3575, 1894, 1426, 41, 451):
    r = sm[g]; h = ha[g]; ch = 2*int(r["ha_joint_size"]) + int(r["ha_sum_size"]) if r["ha_sum_size"] and r["ha_joint_size"] else None
    print(f"   g{g} {cost[g]} {h['Ds']} {h['Dc']} {r['ha_sum_size']} {r['ha_carry_size']} {r['ha_joint_size']}({r['ha_joint_status'][:3]}) | {fc[g]['lb']} {fc[g]['ub']} {fc[g]['status'][:3]} | {fj[g]['lb']} {fj[g]['ub']} {ch}")
print("== premium")
P = {}; Pm = {}; Pf = {}; Pfl = {}
for g in reps4:
    r = sm[g]
    if r["ha_joint_status"] == "OPTIMAL":
        P[g] = int(r["ha_joint_size"]) * cost[g] / 84
    mb = min(int(sm[m]["mul_size"]) for m in members4[g]); Pm[g] = mb * cost[g] / 36
    Pf[g] = best[g] * cost[g] / 72; Pfl[g] = best[g] * cost[g] / 84
P961 = {g: int(sm[g]["ha_joint_size"]) * cost[g] / 84 for g in reps4 if sm[g]["ha_joint_size"]}
print(f"  HA premium over {len(P961)} classes with a known joint circuit: min {min(P961.values()):.2f} max {max(P961.values()):.2f} median {med(P961.values()):.2f}; median transistors {med(int(sm[g]['ha_joint_size'])*cost[g] for g in P961)}")
print(f"  HA premium over {len(P)} classes: min {min(P.values()):.2f} max {max(P.values()):.2f} median {med(P.values()):.2f}; min transistors {min(int(sm[g]['ha_joint_size'])*cost[g] for g in P)}")
print(f"  product premium: min {min(Pm.values()):.2f} max {max(Pm.values()):.2f} median {med(Pm.values()):.2f}")
print(f"  FA premium vs 72: min {min(Pf.values()):.2f} max {max(Pf.values()):.2f} median {med(Pf.values()):.2f}")
print("  cheapest HA classes:", sorted((int(sm[g]['ha_joint_size'])*cost[g], g, lc[g]['min_cells'], cost[g], sm[g]['ha_joint_size'], round(P[g], 2)) for g in P)[:8])
medc = med(cs); print("  median-class row: cells 7? cost 52, joint 10 -> 520; median of S*c:", med([int(sm[g]['ha_joint_size'])*cost[g] for g in P]))
for g in (8431, 3394, 6640, 7471, 281, 451):
    c4 = int(sm[g]["canon4"]); mb = min(int(sm[m]["mul_size"]) for m in members4[c4]); j = sm[c4]["ha_joint_size"]
    print(f"  g{g} class {c4}: c={cost[c4]} S_joint={j} P_L={int(j)*cost[c4]/84:.2f} P_E={int(j)*cost[c4]/42:.2f} S_mul(best)={mb} P_mul={mb*cost[c4]/36:.2f} FA UB={best[c4]} [LB {fj[c4]['lb']}] P_FA={best[c4]*cost[c4]/72:.2f}")
print("== spectrum")
S = {}
for s in (8, 9, 10):
    S[s] = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/spectrum_S{s}.csv"))}
    print(f"  S={s}: gates {len(S[s])} complete {sum(r['full']=='1' for r in S[s].values())} nodes {sum(int(r['nodes']) for r in S[s].values()):.3e} seconds {sum(float(r['seconds']) for r in S[s].values()):.0f} median s/gate {med([float(r['seconds']) for r in S[s].values()]):.2f} mean {statistics.mean([float(r['seconds']) for r in S[s].values()]):.2f}")
s10 = S[10]; s9 = S[9]
reps12 = sorted({int(r["canon12"]) for r in sm.values()}); members12 = collections.defaultdict(list)
for g, r in sm.items(): members12[int(r["canon12"])].append(g)
print("  S10 reps covered", sum(g in s10 for g in reps12), "unresolved-sum gates covered", sum(g in s10 for g, r in sm.items() if r["ha_sum_status"] != "OPTIMAL"), "overlap reps∩unresolved", sum(1 for g, r in sm.items() if r["ha_sum_status"] != "OPTIMAL" and int(r["canon12"]) == g))
diam_class = {}
for g in reps12:
    d = s10[g]["diameter"]; diam_class[g] = int(d) if d else 11
pg = C(); pc = C()
for g in reps12:
    pc[diam_class[g]] += 1; pg[diam_class[g]] += len(members12[g])
print("  diameter per class", dist(pc), "per gate", dist(pg), "share >=11", pg[11]/3774)
unres = [g for g, r in sm.items() if r["ha_sum_status"] != "OPTIMAL"]
print("  unresolved sums: in S10 h_sum values", dist(C(s10[g]["h_sum"] for g in unres if g in s10)), "all gates with diameter>=11 class:", all(diam_class[int(sm[g]["canon12"])] == 11 for g in unres))
print("  S10 nodes per gate min/max", min(int(r["nodes"]) for r in s10.values()), max(int(r["nodes"]) for r in s10.values()))
full9 = [r for r in s9.values() if r["full"] == "1"]
print("  S9 complete", len(full9), "mean size range", min(float(r["mean_size_reached"]) for r in full9), max(float(r["mean_size_reached"]) for r in full9), "g8431", s9[8431]["mean_size_reached"], s9[8431]["full"], "g4066", s9[4066]["mean_size_reached"], s9[4066]["full"], "g700 reached", s9[700]["reached"], "carry", sm[700]["ha_carry_size"], "g700 diameter class", diam_class[int(sm[700]["canon12"])])
hist = [list(map(int, r["hist"].split())) for r in s9.values()]
cum = [[sum(h[:k+1]) for k in range(len(h))] for h in hist]
print("  S9 median cumulative by s:", [med(c[k] for c in cum) for k in range(10)])
print("  S9 half-size dist", dist(C(r["half_size"] for r in s9.values())))
# agreement counts & spearman
pairs = set()
for s in (8, 9, 10):
    rows = S[s]
    for t, col, stat in (("ha_sum", "h_sum", "ha_sum"), ("ha_carry", "h_carry", "ha_carry"), ("mul", "mul", "mul")):
        agree = dis = 0; xs = []; ys = []; xd = []; yd = []
        for g, r in rows.items():
            gs = int(r[col]); cp = sm[g][f"{stat}_size"]; st = sm[g][f"{stat}_status"]
            if gs > 0 and st == "OPTIMAL":
                if gs == int(cp): agree += 1
                else: dis += 1
            if st == "OPTIMAL" and gs > 0:  # table: gates realising the target within S, proven
                xs.append(float(r["mean_size_reached"])); ys.append(int(cp)); pairs.add((g, t))
            if st == "OPTIMAL" and r["full"] == "1" and r["diameter"]:
                xd.append(int(r["diameter"])); yd.append(int(cp))
        print(f"  S={s} {t}: GPU/CP-SAT agree {agree} disagree {dis}; spearman mean-size {spearman(xs, ys):.2f} (n={len(xs)}) diameter {spearman(xd, yd):.2f} (n={len(xd)})")
print("  cross-checked (gate, target) instances over S=8,9,10:", len(pairs), dict(C(t for g, t in pairs)))
print("== misc")
O = json.load(open(f"{R}/orbits.json")); print("  orbits:", {k: v for k, v in O.items() if k != "fix"}); print("  fix:", O["fix"])
K = json.load(open(f"{R}/k4_timing.json")); print("  k4:", {k: v for k, v in K.items() if k != "fix"})
E = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/enumerate.csv"))}
print("  DFA_carry (2Ds+Dc) for 8431:", 2*int(ha[8431]["Ds"])+int(ha[8431]["Dc"]), "GFA_tree 8431", ha[8431]["GFA_tree"], "Gs_tree/Gc_tree", ha[8431]["Gs_tree"], ha[8431]["Gc_tree"])
print("  joint circuit 4066:", json.load(open(f"{R}/synth/ha_joint/4066.json"))["gates"], json.load(open(f"{R}/synth/ha_joint/4066.json"))["outputs"])
print("  mul 3-gate circuits:", [(g, json.load(open(f"{R}/synth/mul/{g}.json"))["gates"]) for g in (6733, 7471)])
print("  sum circuit 8431:", json.load(open(f"{R}/synth/ha_sum/8431.json"))["gates"])
print("  e8:", open(f"{R}/e8_adders.csv").read())
