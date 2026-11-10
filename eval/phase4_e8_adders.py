#!/usr/bin/env python3
"""E8: N-bit-equivalent adder comparison, binary vs balanced ternary, in transistor cost
and in stage depth, under Etiemble's equal-information rule (N bits <-> ceil(N/log2 3) trits).

Cost sources (data/cell_costs.json + results):
  binary FA: 28 T (complementary CMOS, Etiemble 2021), 36 T (9-NAND), 14 T HA;
  ternary FA: Etiemble's best mux/succ-pred design 72 T (2 supplies) / 78 T (1 supply);
              single-universal-gate FA = (#gates of the best single-gate FA) x (cost of that gate in L**)
              — read from results/synth/fa_joint and results/libcost when present.
Depth: ripple-carry = stages x per-stage carry depth (gate levels: binary 9-NAND FA carry
depth 3 [textbook], ternary single-gate FA carry depth from synthesis). Prefix adders: carry
levels ceil(log2(stages)); the ternary saving is log2(stages_bin/stages_tern) ~ 0.66 level.
Writes results/e8_adders.csv and results/e8_adders.md.
"""
import csv, json, math, os, glob

R = "results"
C = json.load(open("data/cell_costs.json"))
BIN_FA, BIN_FA_NAND, BIN_HA = C["binary_reference"]["FA_cmos"], C["binary_reference"]["FA_nand9"], C["binary_reference"]["HA_mux"]
T_FA_ETI = C["ternary_reference_adders"]["FA_best_2PS"]

def trits(nbits): return math.ceil(nbits / math.log2(3))

# best single-gate FA (joint sum+carry) from Stage B, and its gate cost from E7
def best_single_gate_fa():
    recs = []
    for p in glob.glob(f"{R}/synth/fa_joint/*.json"):
        r = json.load(open(p))
        if r.get("size"): recs.append(r)
    if not recs: return None
    costs = {}
    for p in glob.glob(f"{R}/libcost/*.json"):
        r = json.load(open(p)); v = r.get("costs", {}).get("lin2011")
        if v: costs[r["gate"]] = v["transistors"]
    best = None
    for r in recs:
        gc = costs.get(r["gate"])
        if gc is None: continue
        tot = r["size"] * gc
        if best is None or tot < best["transistors"]:
            best = {"gate": r["gate"], "fa_gates": r["size"], "fa_status": r["status"], "gate_T": gc, "transistors": tot,
                    "carry_depth": r.get("depth_of_size_opt")}
    return best

bsg = best_single_gate_fa()
rows = []
for N in [4, 8, 16, 32, 64]:
    t = trits(N)
    row = {"N_bits": N, "trits": t,
           "bin_RCA_T_cmos": N * BIN_FA, "bin_RCA_T_nand": N * BIN_FA_NAND,
           "tern_RCA_T_etiemble": t * T_FA_ETI,
           "tern_RCA_T_single_gate": (t * bsg["transistors"]) if bsg else None,
           "ratio_etiemble_vs_cmos": round(t * T_FA_ETI / (N * BIN_FA), 3),
           "ratio_single_vs_cmos": round(t * bsg["transistors"] / (N * BIN_FA), 3) if bsg else None,
           "bin_RCA_carry_levels_nand": 3 * N,            # textbook 9-NAND FA: carry depth 3
           "tern_RCA_carry_levels_single": (bsg["carry_depth"] * t) if bsg and bsg.get("carry_depth") else None,
           "prefix_levels_bin": math.ceil(math.log2(N)), "prefix_levels_tern": math.ceil(math.log2(t)),
           "prefix_level_saving": round(math.log2(N / t), 3)}
    rows.append(row)
os.makedirs(R, exist_ok=True)
with open(f"{R}/e8_adders.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
md = ["# E8 — adders at equal information (transistors; Etiemble's rule)\n",
      f"- binary FA: {BIN_FA} T (CMOS) / {BIN_FA_NAND} T (9-NAND); ternary FA: Etiemble best {T_FA_ETI} T; "
      + (f"best single-gate FA: g{bsg['gate']} x{bsg['fa_gates']} gates x {bsg['gate_T']} T = {bsg['transistors']} T ({bsg['fa_status']})" if bsg else "single-gate FA: pending Stage B / E7"),
      "\n| N | trits | bin RCA T | tern RCA T (Etiemble) | tern RCA T (single gate) | ratio Eti/CMOS | ratio single/CMOS | prefix levels bin/tern |", "|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append(f"| {r['N_bits']} | {r['trits']} | {r['bin_RCA_T_cmos']} | {r['tern_RCA_T_etiemble']} | {r['tern_RCA_T_single_gate']} | {r['ratio_etiemble_vs_cmos']} | {r['ratio_single_vs_cmos']} | {r['prefix_levels_bin']}/{r['prefix_levels_tern']} |")
md.append("\nPrefix (Brent–Kung/Kogge–Stone) carry-level saving of ternary = log2(N/trits) ≈ 0.66 level, independent of N; "
          "the information-density advantage does not compound in log-depth adders.")
open(f"{R}/e8_adders.md", "w").write("\n".join(md) + "\n"); print("\n".join(md))
