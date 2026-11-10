#!/usr/bin/env python3
"""Recompute every Stage A number quoted in paper/sec_results.tex from the FRESH results/synth_ha.csv
and results/synth_summary.csv (never from *_pre_batch_*)."""
import csv, collections, sys
R = sys.argv[1] if len(sys.argv) > 1 else "results"
ha = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_ha.csv"))}
sm = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_summary.csv"))}
assert len(ha) == 3774 and len(sm) == 3774, (len(ha), len(sm))
I = lambda s: int(s) if s not in ("", None) else None
C = collections.Counter
def dist(c): return "{" + ", ".join(f"{k}: {v}" for k, v in sorted(c.items())) + "}"
# depths
Ds = C(int(r["Ds"]) for r in ha.values()); Dc = C(int(r["Dc"]) for r in ha.values())
print("Ds", dist(Ds)); print("Dc", dist(Dc))
heat = C((int(r["Ds"]), int(r["Dc"])) for r in ha.values())
print("heat top", heat.most_common(6), " (2,4):", heat[(2, 4)])
print("DFA_carry", dist(C(int(r["DFA_carry"]) for r in ha.values())))
# sizes
for t in ("ha_sum", "ha_carry", "ha_joint", "mul"):
    st = C(r[f"{t}_status"] for r in sm.values())
    sz = C(I(r[f"{t}_size"]) for r in sm.values() if r[f"{t}_status"] == "OPTIMAL")
    lb = C(I(r[f"{t}_lb"]) for r in sm.values() if r[f"{t}_status"] != "OPTIMAL")
    print(f"{t}: status {dict(st)}; proven sizes {dist(sz)}; LB of unproven {dist(lb)}")
    if t in ("ha_joint",):
        szall = C(I(r[f"{t}_size"]) for r in sm.values() if r[f"{t}_size"])
        print(f"   {t} size (all, incl. feasible UB) {dist(szall)}")
# proven both sum & carry
both = [g for g, r in sm.items() if r["ha_sum_status"] == "OPTIMAL" and r["ha_carry_status"] == "OPTIMAL"]
print("both sum&carry proven:", len(both))
tot8 = [g for g in both if int(sm[g]["ha_sum_size"]) + int(sm[g]["ha_carry_size"]) == 8]
print("sum+carry = 8:", len(tot8), "classes(canon4):", sorted({sm[g]["canon4"] for g in tot8}), "e.g.", tot8[:8])
# joint savings
sav = C(int(sm[g]["ha_sum_size"]) + int(sm[g]["ha_carry_size"]) - int(sm[g]["ha_joint_size"])
        for g in both if sm[g]["ha_joint_status"] == "OPTIMAL")
print("joint saving (all three proven):", dist(sav), "n", sum(sav.values()))
jmin = min(int(r["ha_joint_size"]) for r in sm.values() if r["ha_joint_status"] == "OPTIMAL")
jm = [g for g, r in sm.items() if r["ha_joint_status"] == "OPTIMAL" and int(r["ha_joint_size"]) == jmin]
print("min joint", jmin, "gates", jm, "classes", sorted({sm[g]["canon4"] for g in jm}))
# class invariance
def classes(key, t, proven_only=True):
    by = collections.defaultdict(set); n = collections.defaultdict(int)
    for g, r in sm.items():
        if proven_only and r[f"{t}_status"] != "OPTIMAL": continue
        by[r[key]].add(r[f"{t}_size"]); n[r[key]] += 1
    return by
jc = classes("canon4", "ha_joint"); print("ha_joint: canon4 classes with a proven member", len(jc), "constant on", sum(len(v) == 1 for v in jc.values()))
mc = classes("canon4", "mul"); print("mul: canon4 classes", len(mc), "non-constant", sum(len(v) > 1 for v in mc.values()))
# swap classes for mul
def label(tbl): return sum({"-": 0, "0": 1, "+": 2}[ch] * 3**i for i, ch in enumerate(tbl))
def swap(tbl): return "".join(tbl[3 * y + x] for x in range(3) for y in range(3))
sw = collections.defaultdict(set)
for g, r in sm.items():
    t = r["table"]; sw[min(label(t), label(swap(t)))].add(r["mul_size"])
print("mul: swap classes", len(sw), "non-constant", sum(len(v) > 1 for v in sw.values()))
m3 = [g for g, r in sm.items() if r["mul_size"] == "3"]; print("mul size 3 gates:", m3)
# table tab:ha
print("tab:ha  gate Ds Ss Dc Sc Sjoint(status) 2Ds+Dc Smul")
for g in (4066, 8431, 8242, 7471, 451, 1894, 1426, 41, 6640):
    r = sm[g]; h = ha[g]
    print(f"  g{g} {r['table']} {h['Ds']} {r['ha_sum_size'] or 'UNK(lb '+r['ha_sum_lb']+')'} {h['Dc']} {r['ha_carry_size']} {r['ha_joint_size']}({r['ha_joint_status'][:3]}) {2*int(h['Ds'])+int(h['Dc'])} {r['mul_size']}")
# the 266 unresolved sums
unk = [g for g, r in sm.items() if r["ha_sum_status"] != "OPTIMAL"]
print("ha_sum unresolved:", len(unk), "canon4 classes", len({sm[g]["canon4"] for g in unk}), "canon12 classes", len({sm[g]["canon12"] for g in unk}),
      "their Ds", dist(C(int(ha[g]["Ds"]) for g in unk)), "their carry sizes", dist(C(int(sm[g]["ha_carry_size"]) for g in unk)))
# fa (stage B, pass-1 provisional): reps only
fa = [r for r in sm.values() if r["fa_carry_status"]]
print("fa rows (reps):", len(fa), "fa_carry status", dict(C(r["fa_carry_status"] for r in fa)), "fa_joint status", dict(C(r["fa_joint_status"] for r in fa)))
