# Which ternary gate should be the NAND?

Code and raw results for

> R. P. Das, J. Mishra, S. K. Sahay, A. Pathak, L. K. Vashishtha and S. Mishra, *Which ternary gate should be the NAND? Exact synthesis of balanced-ternary arithmetic from every universal two-input gate, and the price of single-gate universality*, manuscript submitted to Integration, the VLSI Journal, 2026.

Of the 19,683 two-input ternary gates, 3,774 are functionally complete (Sheffer). The paper asks which of them is the best primitive for balanced-ternary arithmetic and what insisting on a single gate type costs. Every number, table and figure in the manuscript is regenerated from the files in `results/` by the scripts in `eval/`; `results/` is the output of one clean batch on one machine, produced by the scripts in `scripts/`, `src/`, `synth/` and `gpu/`.

## Contents

| path | what it is |
|---|---|
| `src/main.rs`, `Cargo.toml` | Rust program `univ`: enumeration of all 19,683 gates, the three universality tests, orbit counts (Burnside), breadth-first minimum-depth synthesis of the half adder, the depth-2 lower-bound check, the single-thread timing harness, and the four-valued count (`k4`). |
| `synth/exact.py` | CP-SAT (OR-Tools) exact synthesis of k-valued circuits over a fixed gate library: minimum size (DAG model), minimum depth, minimum cost; hint-seeded upper-bound improvement for the full adder. |
| `synth/run_sweep.py` | Resumable sweep over gates and tasks (`ha_sum`, `ha_carry`, `ha_joint`, `mul`, `fa_carry`, `fa_joint`); one JSON per (gate, task) in `results/synth/<task>/<gate>.json`. |
| `synth/run_libcost.py`, `synth/libs.py` | Cost of each universal gate over the cell library L** = {STI, NTI, PTI, TNAND, TNOR, C1, INC, DEC}, in three CNTFET transistor-count variants (`data/cell_costs.json`). |
| `gpu/spectrum.cu` | CUDA exhaustive enumeration of every DAG circuit of up to S instances of one gate; records the minimum size of each of the 19,683 two-input functions. `gpu/validate.py` cross-checks the output against CP-SAT. |
| `eval/` | Aggregation and reporting: `phase1_report.py` (universality), `phase2_report.py` (synthesis), `phase4_a_targets.py` (library optima of the targets), `phase4_e8_adders.py`, `phase4_e9_multipliers.py` (equal-information comparisons), `phase5_spectrum.py` (size spectrum), `cell_set_completeness.py` (Slupecki test of cell sets), `stageA_check.py` and `audit_numbers.py` (recompute every number quoted in the paper), `make_figures.py` (all data figures), `tikz_circuits.py` (circuit diagrams and the size-diameter table), `truth_tables.py` (the truth-table block of Table 1), `gate_lists.py` (the gate lists of Appendix C), `exposure_check.py` (clean-batch protocol). |
| `scripts/` | Batch drivers used on the experiment machine: `make_batch.sh` (whole batch, resumable), `run_all.sh` (phase 1), `run_phase2.sh` (CP-SAT sweeps), `run_phase4.sh` (library costs and analyses), `run_pipeline.sh`, `clean_rerun.sh` (clean-or-redo orchestrator), `ctl.sh`, `batch_shard.sh`, `queue_pipeline.sh`. |
| `data/cell_costs.json` | Transistor counts per cell for the three cost variants and the binary and ternary reference designs, with sources. |
| `data/universal_gates.txt` | The list of 3,774 universal gates from the preliminary version of the study (used only as a cross-check). |
| `results/` | Raw outputs of the clean batch (see below). |

## Conventions

A gate g : T^2 -> T with T = {-, 0, +} is stored as nine trits in row-major order over (x, y), with the digit map - -> 0, 0 -> 1, + -> 2. Its label is sum_i d_i 3^i with entry i = 3x + y the units place for i = 0. The table string prints the nine entries in the same order; for example g8431 is `0+--+0+-0`, that is rows `0+-`, `-+0`, `+-0`. Circuits are lists of `[type, left, right]` with operands `x0`, `x1`, `x2` (inputs) or `gK` (output of the K-th instance); unary cells repeat the operand, constants use `x0` twice.

## Results files

| file | produced by | content |
|---|---|---|
| `results/enumerate.csv` | `univ enumerate` | one row per gate: clone size, unary closure size, the Davies/Rousseau test, structural flags, canonical forms under S3xZ2 (`canon12`) and Z2xZ2 (`canon4`). |
| `results/orbits.json` | `univ orbits` | orbit counts and Burnside fixed-point counts. |
| `results/lower_bounds.json` | `univ lowerbound` | gates realising h_sum / h_carry at depth <= 2, over all 19,683 gates (universal or not). |
| `results/synth_ha.csv` | `univ synth` | exact minimum depths of h_sum and h_carry for every universal gate (breadth-first search over truth tables) and formula-size upper bounds. |
| `results/timing.json`, `results/k4_timing.json` | `univ timing`, `univ k4` | single-thread timings (medians of 10 runs) and the four-valued count. |
| `results/synth/<task>/<gate>.json` | `synth/run_sweep.py` | CP-SAT result per gate and task: status (`OPTIMAL`, `FEASIBLE_LB_UNPROVEN`, `UNKNOWN`, `BOUNDS`), size, lower bound, circuit, time limit, wall time. |
| `results/synth_summary.csv` | `eval/phase2_report.py` | one row per gate collecting all tasks. |
| `results/libcost/<gate>.json` | `synth/run_libcost.py` | cell minimum and transistor minima of each Z2xZ2 representative over L**. |
| `results/libcost_targets.json` | `eval/phase4_a_targets.py` | library optima of h_sum, h_carry, the joint half adder and the trit product. |
| `results/gpu_spectrum_S{8,9,10}/<gate>.json` | `gpu/spectrum` | per gate: minimum size of every function (19,683-entry string), per-size counts, node count, seconds. |
| `results/spectrum_S{8,9,10}.csv` | `eval/phase5_spectrum.py` | per-gate summary: functions reached, size-diameter, mean size, first sizes of h_sum, h_carry and mul. |
| `results/e8_adders.csv`, `results/e9_multipliers.csv` | `eval/phase4_e8_*.py`, `eval/phase4_e9_*.py` | ripple-carry adders and array multipliers at equal information. |
| `results/cell_sets.json` | `eval/cell_set_completeness.py` | Slupecki test of the cell sets in the paper. |
| `results/meta.json` | `scripts/run_all.sh` | machine and toolchain of the batch. |

## Headline numbers (all from `results/`)

- 3,774 universal gates by three independent tests; 322 orbits under S3xZ2, 966 under Z2xZ2 (the cost-invariant classes for addition).
- Half adder, all 3,774 gates: the carry is proven optimal for every gate; the sum for 3,508, and the GPU enumeration certifies that the remaining 266 need more than ten instances. Exactly four gates (the class of g8431) realise the sum with two instances; the class of g4066 has the smallest joint half adder (6 instances).
- Full adder, one representative per Z2xZ2 class: certified intervals; best known two-output circuits 13 (g6640), 16 (g8431), 17 (class of g4066) against 9 NANDs in binary. The chained bound 2 S_joint + S_sum equals the solver's result in 893 of 896 classes and is beaten in 3.
- Size spectrum: every universal gate enumerated to 9 instances, the 322 representatives and the unresolved gates to 10; 10,701 CP-SAT optima cross-checked with zero disagreements; 13.5% of the universal gates need more than ten instances for some function.
- Cost over L** (Lin-Kim-Lombardi counts): 24 to 82 transistors per universal gate (median 52); single-gate half adder 3.1 to 11.8 times the library optimum (g8431: 6.0), against 1.4 for binary NAND.
- At equal information, Etiemble's best ternary ripple-carry adders cost 1.65 to 1.93 times binary; balanced-ternary array multipliers 1.30 to 1.51 times binary (unbalanced: 2.09 to 2.59).

## Reproducing

Machine used: Intel Core i9-13900K (24 cores / 32 threads), 128 GB, Ubuntu 26.04, two GeForce RTX GPUs (3080 and 3060, 12 GB each); Rust 1.93, Python 3.14 with OR-Tools 9.15, CUDA 12.4. Time limits are hard-coded in the scripts and recorded in every result file; the certified bounds (not the proven optima) depend on them and on machine load, so the batch was run under the clean-or-redo protocol described in Appendix B of the paper (`scripts/clean_rerun.sh`, `eval/exposure_check.py`).

```
cargo build --release
./scripts/run_all.sh            # phase 1: enumerate, orbits, lower bounds, depth synthesis, timing  (about 1 h)
./scripts/run_phase2.sh         # k = 4 count; CP-SAT sweeps: half adder and product on all gates, full adder on 966 reps  (about 1.5 days on 32 threads)
./scripts/run_phase4.sh         # library costs of the 966 reps, library optima, adders, multipliers  (about 10 h)
nvcc -O3 -arch=sm_86 -o gpu/spectrum gpu/spectrum.cu && ./gpu/run_gpu.sh   # size spectrum S = 8, 9, 10  (about 31 GPU-hours)
python3 eval/phase5_spectrum.py 8; python3 eval/phase5_spectrum.py 9; python3 eval/phase5_spectrum.py 10
python3 eval/cell_set_completeness.py results
python3 eval/audit_numbers.py results           # prints every number quoted in the paper
python3 eval/make_figures.py results figs      # data figures (PDF)
python3 eval/tikz_circuits.py results figs     # circuit diagrams (TikZ) and the diameter-7 table
python3 eval/truth_tables.py results figs      # truth tables of the targets, recurring gates and cells
python3 eval/gate_lists.py results figs        # commutative gates and class representatives (appendix lists)
```

The scripts assume the layout of this repository with `results/` as the working directory for outputs; the drivers in `scripts/` hard-code the path of the experiment machine (`/extra/universality`) and should be edited before use elsewhere. Every driver is idempotent: finished work is skipped, so an interrupted run can be restarted.

## Cost model

Cell transistor counts follow Lin, Kim and Lombardi (IEEE TNANO 2011) as tabulated by Etiemble (arXiv:1908.06841), with two alternative inverter/NAND styles (Sharifi et al.; You and Nepal) for sensitivity; the binary references (NAND 4 T, half adder 14 T, full adder 28 T) and the ternary reference designs (half adder 42 T, full adder 72 T, unbalanced one-trit multiplier 38 T) are from Etiemble (arXiv:2101.01516, arXiv:1908.06841). See `data/cell_costs.json`.

## Use of AI assistance

Claude (Anthropic) was used to set up the test harnesses and batch scripts, to collect the numbers from the experimental logs and result files, to draw the TikZ diagrams and to typeset the manuscript. The authors reviewed and edited all of it and take full responsibility for the content.

## License

GNU General Public License v3.0 only (no linking or classpath exception), with an additional term under GPLv3 section 7(b): every use, extension or redistribution must preserve the attribution to Jyotiprakash Mishra and cite the author in derived work. The licence text is in `LICENSE`; the copyright notice and the additional attribution term are in `NOTICE`, which must be kept with every copy.
