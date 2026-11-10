#!/usr/bin/env python3
"""Phase 1 report: validates the draft's numbers against E1–E4/E11 results.
Reads results/*.csv|json, writes results/phase1_report.md (stdlib only)."""
import csv, json, collections, os, sys

R = "results"
out = []
P = out.append

def load_csv(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))

# ---------------- E1
en = load_csv(f"{R}/enumerate.csv")
P("# Phase 1 report\n")
P("## E1 — universality tests over all 19,683 gates\n")
full = {r["gate"] for r in en if r["closure_size"] == "19683"}
un = {r["gate"] for r in en if r["unary_size"] == "27"}
rou = {r["gate"] for r in en if r["rousseau"] == "1"}
P(f"- full closure: **{len(full)}** universal; unary closure: **{len(un)}**; Rousseau: **{len(rou)}**")
P(f"- pairwise set equality: full==unary {full==un}, full==Rousseau {full==rou}")
paper = {l.strip() for l in open("data/universal_gates_paper.txt") if l.strip()}
mine_tab = {r["table"] for r in en if r["gate"] in full}
P(f"- paper list: {len(paper)} rows; ours: {len(mine_tab)}; only-ours {len(mine_tab-paper)}, only-paper {len(paper-mine_tab)}")
if mine_tab != paper:
    tr = lambda t: "".join(t[3*(i%3)+i//3] for i in range(9))
    paperT = {tr(t) for t in paper}
    P(f"- transposed comparison: only-ours {len(mine_tab-paperT)}, only-paper {len(paperT-mine_tab)}")
# clone sizes of non-universal gates
sizes = collections.Counter(int(r["closure_size"]) for r in en if r["gate"] not in full)
P(f"- distinct clone sizes among non-universal gates: {len(sizes)}; largest: {sorted(sizes)[-5:]}; smallest: {sorted(sizes)[:5]}")
tot_ops = sum(int(r["closure_ops"]) for r in en)
P(f"- total compositions in full-closure test: {tot_ops:,}; unary-closure: {sum(int(r['unary_ops']) for r in en):,}")
U = [r for r in en if r["gate"] in full]
P("\n### Structural properties of the universal gates\n")
P("| property | count | % |\n|---|---|---|")
for k, lab in [("surjective","surjective"),("commutative","commutative"),("self_dual","self-dual (negation automorphism)"),
               ("inc_invariant","Inc-invariant (3-cycle automorphism)"),("zero_preserving","zero-preserving g(0,0)=0"),("diag_bijective","diagonal bijective")]:
    c = sum(r[k]=="1" for r in U); P(f"| {lab} | {c} | {100*c/len(U):.1f} |")
fp = collections.Counter(r["diag_fixed_points"] for r in U)
P(f"\n- diagonal fixed points distribution (universal): {dict(fp)}  (Rousseau ⇒ must be all 0)")
ea = collections.Counter(r["essential_arity"] for r in U)
P(f"- essential arity (universal): {dict(ea)}  (must be all 2)")
# why non-universal: which Rousseau condition fails
fails = collections.Counter((r["no_subalg"], r["no_autom"], r["simple"]) for r in en if r["gate"] not in full)
P("\n### Why gates fail (Rousseau conditions: no_subalg, no_autom, simple)\n")
for k, v in sorted(fails.items(), key=lambda x: -x[1]): P(f"- {k}: {v}")

# ---------------- E2
if os.path.exists(f"{R}/orbits.json"):
    ob = json.load(open(f"{R}/orbits.json"))
    P("\n## E2 — orbits\n")
    for k in ["image_of_universal_is_universal","orbits12_all","orbits12_universal","orbits4_all","orbits4_universal",
              "burnside_orbits_all","burnside_orbits_univ","burnside4_orbits_univ","class_size_hist_univ"]:
        P(f"- {k}: {ob[k]}")

# ---------------- E11
if os.path.exists(f"{R}/lower_bounds.json"):
    lb = json.load(open(f"{R}/lower_bounds.json"))
    P("\n## E11 — depth lower bounds (all 19,683 gates)\n")
    P(f"- gates realising h_sum at depth ≤2: {lb['n_h_sum_depth_le2']}  → {lb['h_sum_depth_le2_gates'][:20]}")
    P(f"- gates realising h_carry at depth ≤2: {lb['n_h_carry_depth_le2']} → {lb['h_carry_depth_le2_gates'][:20]}")
    P(f"- depth-1: h_sum {lb['h_sum_depth1_gates']}, h_carry {lb['h_carry_depth1_gates']}")

# ---------------- E4
if os.path.exists(f"{R}/synth_ha.csv"):
    sy_all = load_csv(f"{R}/synth_ha.csv")
    sy = [r for r in sy_all if r["Ds"] != "" and r["Dc"] != ""]   # exact depths available
    syd = [r for r in sy if r["Gs_dag"] != "" and r["Gc_dag"] != ""]  # DP sizes within bound
    P("\n## E4 — half-adder synthesis for all universal gates\n")
    P(f"- rows: {len(sy_all)}; exact depths for {len(sy)} gates; DP sizes (≤10) for {len(syd)} gates")
    def I(r,k): return int(r[k])
    P(f"- D_s distribution: {dict(sorted(collections.Counter(I(r,'Ds') for r in sy).items()))}")
    P(f"- D_c distribution: {dict(sorted(collections.Counter(I(r,'Dc') for r in sy).items()))}")
    P(f"- G_s(tree) distribution: {dict(sorted(collections.Counter(I(r,'Gs_tree') for r in sy).items()))}")
    P(f"- G_s(dag,DP≤10) distribution: {dict(sorted(collections.Counter(I(r,'Gs_dag') for r in syd).items()))} (+{len(sy)-len(syd)} beyond bound)")
    P(f"- DFA_carry (=2Ds+Dc) distribution: {dict(sorted(collections.Counter(I(r,'DFA_carry') for r in sy).items()))}")
    P(f"- GFA_tree (=3Gs+2Gc) min: {min(I(r,'GFA_tree') for r in sy)}; GFA_dag(DP) min: {min(I(r,'GFA_dag') for r in syd)}")
    g451 = next((r for r in sy if r["gate"]=="451"), None)
    if g451: P(f"- g451: Ds={g451['Ds']} Gs_tree={g451['Gs_tree']} Dc={g451['Dc']} Gc_tree={g451['Gc_tree']} (paper: 3,5,4,7); expr_sum={g451['expr_sum']}; expr_carry={g451['expr_carry']}")
    P("\n### Best gates (depth-first ordering: DFA_carry, then GFA_tree)\n")
    P("| gate | table | Ds | Gs_t | Dc | Gc_t | DFA | GFA_t | Gs_dag | Gc_dag | GFA_dag | comm | canon12 |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    tabs = {r["gate"]: r["table"] for r in en}
    for r in sorted(sy, key=lambda r:(I(r,'DFA_carry'),I(r,'GFA_tree'),I(r,'gate')))[:15]:
        P(f"| {r['gate']} | `{tabs[r['gate']]}` | {r['Ds']} | {r['Gs_tree']} | {r['Dc']} | {r['Gc_tree']} | {r['DFA_carry']} | {r['GFA_tree']} | {r['Gs_dag']} | {r['Gc_dag']} | {r['GFA_dag']} | {r['commutative']} | {r['canon12']} |")
    P("\n### Best gates (size-first ordering: GFA_dag, then DFA_carry)\n")
    P("| gate | table | Gs_dag | Gc_dag | GFA_dag | Ds | Dc | DFA | canon12 |\n|---|---|---|---|---|---|---|---|---|")
    for r in sorted(syd, key=lambda r:(I(r,'GFA_dag'),I(r,'DFA_carry'),I(r,'gate')))[:15]:
        P(f"| {r['gate']} | `{tabs[r['gate']]}` | {r['Gs_dag']} | {r['Gc_dag']} | {r['GFA_dag']} | {r['Ds']} | {r['Dc']} | {r['DFA_carry']} | {r['canon12']} |")
    # paper's table
    P("\n### The draft's Table (half-adder best gates) re-evaluated\n")
    for g in ["451","1391","1184","1153","1156","1138"]:
        r = next((r for r in sy if r["gate"]==g), None)
        P(f"- g{g}: " + (f"Ds={r['Ds']} Gs={r['Gs_tree']} Dc={r['Dc']} Gc={r['Gc_tree']} DFA={r['DFA_carry']} GFA={r['GFA_tree']}" if r else "NOT UNIVERSAL / missing"))
    # class homogeneity
    P("\n### Class homogeneity (A4 check)\n")
    key = lambda r: (r['Ds'],r['Gs_tree'],r['Dc'],r['Gc_tree'])   # exact-depth fields only
    for cname in ["canon12","canon4"]:
        groups = collections.defaultdict(set)
        for r in sy: groups[r[cname]].add(key(r))
        inhom = {c:v for c,v in groups.items() if len(v)>1}
        P(f"- {cname}: {len(groups)} classes, **{len(inhom)} inhomogeneous** (different HA costs inside one class)")
        if cname=="canon12" and inhom:
            ex = sorted(inhom.items(), key=lambda kv:-len(kv[1]))[:5]
            for c,v in ex: P(f"  - class {c}: costs (Ds,Gs_t,Dc,Gc_t,Gs_d,Gc_d) = {sorted(v)}")
            # did the best gate's class contain worse gates / did any class rep miss a better gate?
            best = min(I(r,'DFA_carry') for r in sy)
            bestgates = [r for r in sy if I(r,'DFA_carry')==best]
            P(f"  - gates achieving min DFA_carry={best}: {len(bestgates)} gates in {len({r['canon12'] for r in bestgates})} S3xZ2 classes / {len({r['canon4'] for r in bestgates})} Z2xZ2 classes (draft: 4 classes)")

# ---------------- E3
if os.path.exists(f"{R}/timing.json"):
    tm = json.load(open(f"{R}/timing.json"))
    P("\n## E3 — timing (single thread)\n")
    for t in tm: P(f"- {json.dumps(t)}")

open(f"{R}/phase1_report.md","w").write("\n".join(out)+"\n")
print("\n".join(out))
