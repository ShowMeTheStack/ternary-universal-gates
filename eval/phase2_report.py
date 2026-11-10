#!/usr/bin/env python3
"""Aggregate results/synth/<task>/<gate>.json into results/synth_summary.csv and
results/phase2_report.md (stdlib only). Joins with enumerate.csv for tables/classes."""
import csv, json, os, glob, collections

R = "results"
en = {r["gate"]: r for r in csv.DictReader(open(f"{R}/enumerate.csv"))}
tasks = sorted(d for d in os.listdir(f"{R}/synth") if os.path.isdir(f"{R}/synth/{d}"))
recs = collections.defaultdict(dict)   # gate -> task -> rec
for t in tasks:
    for p in glob.glob(f"{R}/synth/{t}/*.json"):
        rec = json.load(open(p)); recs[str(rec["gate"])][t] = rec

cols = ["gate", "table", "canon12", "canon4", "commutative"]
for t in tasks:
    cols += [f"{t}_size", f"{t}_lb", f"{t}_status", f"{t}_depth", f"{t}_mindepth"]
with open(f"{R}/synth_summary.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(cols)
    for g in sorted(recs, key=int):
        row = [g, en[g]["table"], en[g]["canon12"], en[g]["canon4"], en[g]["commutative"]]
        for t in tasks:
            r = recs[g].get(t, {})
            row += [r.get("size"), r.get("lb"), r.get("status"), r.get("depth_of_size_opt"), r.get("min_depth")]
        w.writerow(row)

out = ["# Phase 2 report (exact synthesis)\n"]
P = out.append
for t in tasks:
    rs = [recs[g][t] for g in recs if t in recs[g]]
    st = collections.Counter(r["status"] for r in rs)
    sizes = collections.Counter(r["size"] for r in rs if r.get("size") is not None)
    P(f"## {t}: {len(rs)} gates — status {dict(st)}")
    P(f"- size distribution: {dict(sorted(sizes.items()))}")
    if any(r.get("min_depth") for r in rs):
        P(f"- min-depth distribution: {dict(sorted(collections.Counter(r['min_depth'] for r in rs if r.get('min_depth')).items()))}")
    best = sorted([r for r in rs if r.get("size") is not None], key=lambda r: (r["size"], r.get("min_depth") or 99, r["gate"]))[:12]
    P("\n| gate | table | size | lb | status | depth@size | min depth | wall s |\n|---|---|---|---|---|---|---|---|")
    for r in best:
        P(f"| {r['gate']} | `{en[str(r['gate'])]['table']}` | {r['size']} | {r.get('lb')} | {r['status']} | {r.get('depth_of_size_opt')} | {r.get('min_depth')} | {r.get('wall_size')} |")
    # class homogeneity check (canon4)
    groups = collections.defaultdict(set)
    for r in rs:
        groups[en[str(r["gate"])]["canon4"]].add((r.get("size"), r.get("min_depth")))
    inhom = sum(1 for v in groups.values() if len(v) > 1)
    P(f"\n- Z2xZ2 classes covered: {len(groups)}; inhomogeneous: {inhom}\n")
open(f"{R}/phase2_report.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
