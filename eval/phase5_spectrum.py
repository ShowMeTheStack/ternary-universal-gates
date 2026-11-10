#!/usr/bin/env python3
"""E14 aggregation (size-spectrum stage): size spectrum of every universal gate.
Reads results/gpu_spectrum_S<N>/<gate>.json (GPU exhaustive enumeration), results/enumerate.csv
(classes), optional results/ha_exact.csv (CP-SAT sizes) and writes
  results/spectrum_S<N>.csv       one row per gate: reached, diameter, mean size, hist, h_sum/h_carry/mul
  results/spectrum_S<N>_report.md diameter distribution (per gate and per S3xZ2 class), generation
                                  curve quantiles, correlation with arithmetic cost, certification
Usage: phase5_spectrum.py [S] [results_dir]      (stdlib only; refuses *_pre_batch_* paths)
"""
import json, os, sys, csv, glob, statistics, collections
S = int(sys.argv[1]) if len(sys.argv) > 1 else 9
R = sys.argv[2] if len(sys.argv) > 2 else "results"
assert "pre_batch" not in os.path.abspath(R)
D = f"{R}/gpu_spectrum_S{S}"
NF = 19683
spec = {}
for f in glob.glob(f"{D}/*.json"):
    if f.endswith(".nosym.json"): continue
    try: j = json.load(open(f))
    except Exception: continue
    spec[j["gate"]] = j
if not spec: sys.exit(f"no spectra in {D}")
enum = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/enumerate.csv"))}
exact = {}
if os.path.exists(f"{R}/ha_exact.csv"):
    exact = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/ha_exact.csv"))}
rows = []
for g, j in sorted(spec.items()):
    h = j["hist"]; reached = j["reached"]
    full = reached == NF
    diam = max(i for i, v in enumerate(h) if v) if full else None
    tot = sum(i * v for i, v in enumerate(h)); mean = tot / reached
    cum = 0; n_half = None   # size by which half of all functions are reached
    for i, v in enumerate(h):
        cum += v
        if n_half is None and cum >= NF / 2: n_half = i
    rows.append({"gate": g, "canon12": enum[g]["canon12"], "canon4": enum[g]["canon4"], "commutative": enum[g]["commutative"],
                 "S": j["S"], "reached": reached, "full": int(full), "diameter": diam if full else "",
                 "mean_size_reached": round(mean, 4), "half_size": n_half if n_half is not None else "",
                 "h_sum": j["h_sum"], "h_carry": j["h_carry"], "mul": j["mul"],
                 "hist": " ".join(map(str, h)), "nodes": j["nodes"], "seconds": j["seconds"]})
out = f"{R}/spectrum_S{S}.csv"
with open(out, "w", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
# ---- report
L = [f"# E14 size spectrum, S = {S}: {len(rows)} gates\n"]
full = [r for r in rows if r["full"]]
L.append(f"- gates reaching all {NF:,} functions within {S} gates: {len(full)} / {len(rows)}")
if full:
    dd = collections.Counter(r["diameter"] for r in full)
    L.append(f"- size-diameter distribution (per gate): {dict(sorted(dd.items()))}")
    # per S3xZ2 class (diameter is invariant): take representatives present
    reps = {r["canon12"]: r["diameter"] for r in full if str(r["gate"]) == r["canon12"]}
    if reps: L.append(f"- size-diameter distribution over {len(reps)} S3xZ2 representatives: {dict(sorted(collections.Counter(reps.values()).items()))}")
    best = min(r["diameter"] for r in full); L.append(f"- smallest diameter {best}: gates {[r['gate'] for r in full if r['diameter'] == best][:20]}")
ms = [r["mean_size_reached"] for r in rows]
L.append(f"- mean size over reached functions: min {min(ms):.3f}, median {statistics.median(ms):.3f}, max {max(ms):.3f}")
hs = [r["half_size"] for r in rows if r["half_size"] != ""]
if hs: L.append(f"- size by which half of all functions are reached: {dict(sorted(collections.Counter(hs).items()))}")
# generation curve quantiles
H = [list(map(int, r["hist"].split())) for r in rows]
L.append("\n| s | min N(s) | median N(s) | max N(s) | median cumulative |\n|---|---|---|---|---|")
for s in range(S + 1):
    col = [h[s] for h in H]; cum = [sum(h[:s + 1]) for h in H]
    L.append(f"| {s} | {min(col)} | {statistics.median(col):.0f} | {max(col)} | {statistics.median(cum):.0f} |")
# correlation with arithmetic cost (Spearman via ranks, stdlib)
def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]: j += 1
            for k in range(i, j + 1): r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = rank(x), rank(y); n = len(x); mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")
L.append("\n## Does generation speed predict arithmetic cost? (Spearman rank correlation)\n")
for key in ["h_sum", "h_carry", "mul"]:
    sub = [r for r in rows if r[key] != -1]
    if len(sub) > 10:
        L.append(f"- {key} size vs mean size: rho = {spearman([r['mean_size_reached'] for r in sub], [r[key] for r in sub]):.3f} (n = {len(sub)})")
        fs = [r for r in sub if r["full"]]
        if len(fs) > 10: L.append(f"- {key} size vs diameter: rho = {spearman([r['diameter'] for r in fs], [r[key] for r in fs]):.3f} (n = {len(fs)})")
# certification against CP-SAT
if exact:
    L.append("\n## Brute-force certification of the CP-SAT half-adder / multiplier sizes\n")
    for key, col, st in [("h_sum", "ha_sum_size", "ha_sum_status"), ("h_carry", "ha_carry_size", "ha_carry_status"), ("mul", "mul_size", "mul_status")]:
        eq = ne = res = viol = 0
        for r in rows:
            e = exact.get(r["gate"]);
            if not e or not e.get(col): continue
            cs = int(e[col]); gs = r[key]
            if gs == -1:
                if cs <= S: viol += 1
                continue
            if e.get(st) == "OPTIMAL":
                if gs == cs: eq += 1
                else: ne += 1
            else:
                if gs <= cs: res += 1
                else: viol += 1
        L.append(f"- {key}: equals CP-SAT optimum {eq}; MISMATCH {ne}; resolves non-optimal instance {res}; VIOLATION {viol}")
L.append(f"\n- GPU work: {sum(r['nodes'] for r in rows):,} circuit nodes, {sum(r['seconds'] for r in rows):.0f} s total; per gate median {statistics.median(r['seconds'] for r in rows):.2f} s")
open(f"{R}/spectrum_S{S}_report.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
