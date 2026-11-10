#!/usr/bin/env python3
"""Truth tables (3x3 grids, rows x, columns y) of the arithmetic targets, the best gates and the
cells of L**, for the paper (figs/tab_truth.tex). Gate tables are read from results/enumerate.csv."""
import csv, os, sys
R = sys.argv[1] if len(sys.argv) > 1 else "results"; OUT = sys.argv[2] if len(sys.argv) > 2 else "paper/figs"
os.makedirs(OUT, exist_ok=True)
assert "pre_batch" not in os.path.abspath(R)
E = {int(r["gate"]): r["table"] for r in csv.DictReader(open(f"{R}/enumerate.csv"))}
V = ["-", "0", "+"]; sym = {"-": "$-$", "0": "$0$", "+": "$+$"}
def grid(name, t):   # t: 9 chars, entry 3x+y
    rows = [" & ".join(sym[t[3*x+y]] for y in range(3)) for x in range(3)]
    return ("\\begin{tabular}[t]{c|ccc}" + name + " & $-$ & $0$ & $+$\\\\\\hline " +
            "\\\\ ".join(f"{sym[V[x]]} & {rows[x]}" for x in range(3)) + "\\end{tabular}")
def unary(cells):    # cells: list of (name, [v(-),v(0),v(+)] in 0,1,2)
    head = "\\begin{tabular}[t]{c|ccc}$x$ & $-$ & $0$ & $+$\\\\\\hline "
    return head + "\\\\ ".join(n + " & " + " & ".join(sym[V[v]] for v in t) for n, t in cells) + "\\end{tabular}"
def bin_cell(f): return "".join(V[f(x, y)] for x in range(3) for y in range(3))
TNAND = lambda a, b: 2 - min(a, b); TNOR = lambda a, b: 2 - max(a, b)
row1 = [("$\\hs$", E[5681]), ("$\\hc$", E[16401]), ("$\\mu$", E[15665]), ("$g_{8431}$", E[8431]), ("$g_{4066}$", E[4066]), ("$g_{6640}$", E[6640]), ("$g_{451}$", E[451])]
row2 = [("TNAND", bin_cell(TNAND)), ("TNOR", bin_cell(TNOR)), ("MIN", bin_cell(min)), ("MAX", bin_cell(max))]
cells = [("STI", [2, 1, 0]), ("NTI", [2, 0, 0]), ("PTI", [2, 2, 0]), ("INC", [1, 2, 0]), ("DEC", [2, 0, 1])]
sep = "\\hspace{\\fill}"
out = ("\\scriptsize\\setlength{\\tabcolsep}{3pt}\\renewcommand{\\arraystretch}{1.05}\n" +
       sep.join(grid(n, t) for n, t in row1) + "\\\\[3mm]\n" +
       sep.join(grid(n, t) for n, t in row2) + sep + unary(cells) + "\n")
open(f"{OUT}/tab_truth.tex", "w").write(out); print("wrote tab_truth.tex")
