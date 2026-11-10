#!/usr/bin/env python3
"""Gate lists for the appendix (figs/list_commutative.tex, figs/list_reps.tex, figs/tab_truth_comm.tex):
the 90 commutative universal gates, the 322 S3xZ2 class representatives (lexicographically smallest
members) and truth tables of the commutative gates that recur in the paper. Read from results/enumerate.csv."""
import csv, os, sys
R = sys.argv[1] if len(sys.argv) > 1 else "results"; OUT = sys.argv[2] if len(sys.argv) > 2 else "paper/figs"
os.makedirs(OUT, exist_ok=True)
assert "pre_batch" not in os.path.abspath(R)
E = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/enumerate.csv"))}
U = {g: r for g, r in E.items() if r["closure_size"] == "19683"}
comm = sorted(g for g, r in U.items() if r["commutative"] == "1")
reps = sorted({int(r["canon12"]) for r in U.values()})
assert len(U) == 3774 and len(comm) == 90 and len(reps) == 322
assert all(E[g]["canon12"] == str(g) for g in reps)
comm_reps = [g for g in reps if E[g]["commutative"] == "1"]; assert len(comm_reps) == 15
def numlist(xs): return ", ".join(f"{x}" for x in xs)
open(f"{OUT}/list_commutative.tex", "w").write(numlist(comm) + ".\n")
open(f"{OUT}/list_reps.tex", "w").write(numlist(reps) + ".\n")
V = ["-", "0", "+"]; sym = {"-": "$-$", "0": "$0$", "+": "$+$"}
def grid(name, t):
    rows = [" & ".join(sym[t[3*x+y]] for y in range(3)) for x in range(3)]
    return ("\\begin{tabular}{c|ccc}" + name + " & $-$ & $0$ & $+$\\\\\\hline " +
            "\\\\ ".join(f"{sym[V[x]]} & {rows[x]}" for x in range(3)) + "\\end{tabular}")
show = [223, 5791, 5761, 6559]
for g in show: assert E[g]["commutative"] == "1" and g in U, g
for g in (281, 2630, 8431, 4066, 6640): assert E[g]["commutative"] == "0", g
row = lambda gs: "\\begin{tabular}{@{}c@{\\hspace{10mm}}c@{}}" + " & ".join(grid(f"$g_{{{g}}}$", E[g]["table"]) for g in gs) + "\\end{tabular}"
open(f"{OUT}/tab_truth_comm.tex", "w").write("\\scriptsize\\setlength{\\tabcolsep}{3pt}\\renewcommand{\\arraystretch}{1.05}\n" +
    row(show[:2]) + "\\par\\vspace{3mm}\n" + row(show[2:]) + "\n")
print("commutative", len(comm), "reps", len(reps), "commutative reps", comm_reps)
