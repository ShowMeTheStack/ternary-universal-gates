#!/usr/bin/env python3
"""E9: array/Wallace multipliers at equal information: binary NxN vs unbalanced ternary
(Etiemble: 1-trit multiplier has a carry -> 2 partial-product rows per multiplier row) vs
BALANCED ternary (1-trit product is carry-free -> one row). Counts partial products and the
3:2 (FA) / 2:2 (HA) compressors of a Dadda-style column reduction, then costs them with
cell transistor counts. Writes results/e9_multipliers.csv/.md.

Cell costs: binary AND 6 T, FA 28 T (CMOS) [Etiemble 2021]; ternary FA/HA: Etiemble best
72/42 T; unbalanced 1-trit multiplier 38 T (Etiemble 2019 Table XII); balanced 1-trit
multiplier: cost of MUL over L** from results/libcost_targets.json if present, else a
parameter (default: TNAND-class estimate 20 T, flagged).
"""
import csv, json, math, os

R = "results"
C = json.load(open("data/cell_costs.json"))
BIN_AND, BIN_FA, BIN_HA = C["binary_reference"]["AND"], C["binary_reference"]["FA_cmos"], C["binary_reference"]["HA_mux"]
T_FA, T_HA = C["ternary_reference_adders"]["FA_best_2PS"], C["ternary_reference_adders"]["HA_best_2PS"]
U_MUL = C["ternary_reference_multiplier"]["MUL1_trit_2outputs"]
bal_mul_T, bal_mul_src = 20, "ASSUMED"
p = f"{R}/libcost_targets.json"
if os.path.exists(p):
    d = json.load(open(p)).get("mul", {}).get("lin2011")
    if d: bal_mul_T, bal_mul_src = d["transistors"], "L** CP-SAT"

def dadda_reduce(heights, radix_rows=None):
    """Reduce column heights to <=2 using FAs (3->1 + carry to next column) and HAs (2->1 + carry).
    Greedy Dadda-like: returns (#FA, #HA)."""
    h = list(heights); fa = ha = 0
    while max(h) > 2:
        new = [0] * (len(h) + 1)
        for i, c in enumerate(h):
            n = c
            while n >= 3: fa += 1; n -= 3; new[i] += 1; new[i + 1] += 1
            if n == 2 and (i + 1 < len(h) and h[i + 1] > 2): ha += 1; n -= 2; new[i] += 1; new[i + 1] += 1
            new[i] += n
        h = new[:-1] if new[-1] == 0 else new
    return fa, ha, h

def binary(N):
    heights = [sum(1 for i in range(N) for j in range(N) if i + j == k) for k in range(2 * N - 1)]
    fa, ha, _ = dadda_reduce(heights)
    cpa = 2 * N - 1  # final carry-propagate adder width (approx)
    return {"pp": N * N, "FA": fa, "HA": ha, "T": N * N * BIN_AND + fa * BIN_FA + ha * BIN_HA + cpa * BIN_FA}

def ternary_unbalanced(N):
    # each 1-trit product gives a product trit at k=i+j and a (binary) carry trit at k=i+j+1
    heights = [0] * (2 * N)
    for i in range(N):
        for j in range(N):
            heights[i + j] += 1; heights[i + j + 1] += 1
    fa, ha, _ = dadda_reduce(heights)
    return {"pp": 2 * N * N, "FA": fa, "HA": ha, "T": N * N * U_MUL + fa * T_FA + ha * T_HA + (2 * N) * T_FA}

def ternary_balanced(N):
    heights = [sum(1 for i in range(N) for j in range(N) if i + j == k) for k in range(2 * N - 1)]
    fa, ha, _ = dadda_reduce(heights)
    return {"pp": N * N, "FA": fa, "HA": ha, "T": N * N * bal_mul_T + fa * T_FA + ha * T_HA + (2 * N - 1) * T_FA}

rows = []
for Nb, Nt in [(8, 5), (16, 11), (32, 21), (64, 41)]:
    b, u, s = binary(Nb), ternary_unbalanced(Nt), ternary_balanced(Nt)
    rows.append({"N_bits": Nb, "N_trits": Nt, "bin_pp": b["pp"], "bin_FA": b["FA"], "bin_HA": b["HA"], "bin_T": b["T"],
                 "unbal_pp": u["pp"], "unbal_FA": u["FA"], "unbal_HA": u["HA"], "unbal_T": u["T"],
                 "bal_pp": s["pp"], "bal_FA": s["FA"], "bal_HA": s["HA"], "bal_T": s["T"],
                 "ratio_unbal_bin": round(u["T"] / b["T"], 2), "ratio_bal_bin": round(s["T"] / b["T"], 2)})
with open(f"{R}/e9_multipliers.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
md = [f"# E9 — multipliers at equal information (balanced 1-trit MUL cost = {bal_mul_T} T, {bal_mul_src}; unbalanced 38 T; binary AND 6 T; FA/HA ternary 72/42 T, binary 28/14 T)\n",
      "| bits | trits | binary pp/FA/HA/T | unbalanced tern pp/FA/HA/T | balanced tern pp/FA/HA/T | unbal/bin | bal/bin |", "|---|---|---|---|---|---|---|"]
for r in rows:
    md.append(f"| {r['N_bits']} | {r['N_trits']} | {r['bin_pp']}/{r['bin_FA']}/{r['bin_HA']}/{r['bin_T']} | {r['unbal_pp']}/{r['unbal_FA']}/{r['unbal_HA']}/{r['unbal_T']} | {r['bal_pp']}/{r['bal_FA']}/{r['bal_HA']}/{r['bal_T']} | {r['ratio_unbal_bin']} | {r['ratio_bal_bin']} |")
md.append("\nSanity: Etiemble 2019 reports 8x8 binary 2382 T and 5x5 unbalanced ternary 6190 T with his own cell set (AND 6, FA 36, HA 18; ternary MUL 38, FA 124, HA 66).")
open(f"{R}/e9_multipliers.md", "w").write("\n".join(md) + "\n"); print("\n".join(md))
