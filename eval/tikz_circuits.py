#!/usr/bin/env python3
"""Emit TikZ 'rail' drawings of stored circuits (fresh results/ only) into paper/figs/tikz_*.tex,
plus the table of the fastest generators (figs/tab_delta7.tex).
Rail layout: every signal (input or gate output) is a horizontal rail; gate instances are placed left to
right in topological order, each in its own column; a gate taps its two operand rails with vertical
connections (dot = connection; solid = first argument, dashed = second argument) and starts the rail of
its output. No connection ever passes through a node or a label."""
import json, csv, sys, os, collections
R = sys.argv[1] if len(sys.argv) > 1 else "results"; OUT = sys.argv[2] if len(sys.argv) > 2 else "paper/figs"
os.makedirs(OUT, exist_ok=True)
assert "pre_batch" not in os.path.abspath(R)

def rails(gates, n_in, outputs, in_names, out_names, style="gate", labels=None, dx=0.95, dy=0.42, boxw=0.0):
    m = len(gates)
    y = {f"x{i}": -i * dy for i in range(n_in)}
    for k in range(m): y[f"g{k}"] = -(n_in + k) * dy
    xg = {f"g{k}": k * dx for k in range(m)}
    last_use = {s_: None for s_ in y}
    for k, (t, a, b) in enumerate(gates):
        for s_ in (a, b): last_use[s_] = k * dx
    x_end = (m - 1) * dx + 0.9
    out = []
    # rails
    for s_ in y:
        x0 = -0.35 if s_.startswith("x") else xg[s_]
        is_out = s_ in outputs
        x1 = x_end if is_out else last_use[s_]
        if x1 is None: continue
        out.append(f"\\draw[rail] ({x0:.2f},{y[s_]:.2f}) -- ({x1:.2f},{y[s_]:.2f});")
    for i in range(n_in):
        out.append(f"\\node[sig,anchor=east] at (-0.4,{y[f'x{i}']:.2f}) {{${in_names[i]}$}};")
    # taps and gates
    for k, (t, a, b) in enumerate(gates):
        x = xg[f"g{k}"]; yg = y[f"g{k}"]
        if a == b:
            out.append(f"\\draw[tap] ({x:.2f},{y[a]:.2f}) -- ({x:.2f},{yg:.2f}); \\fill ({x:.2f},{y[a]:.2f}) circle (1.3pt);")
        else:
            xa, xb = x - 0.11, x + 0.11
            out.append(f"\\draw[tap] ({xa:.2f},{y[a]:.2f}) -- ({xa:.2f},{yg:.2f}); \\fill ({xa:.2f},{y[a]:.2f}) circle (1.3pt);")
            out.append(f"\\draw[tap,dashed] ({xb:.2f},{y[b]:.2f}) -- ({xb:.2f},{yg:.2f}); \\fill ({xb:.2f},{y[b]:.2f}) circle (1.3pt);")
        lab = labels[k] if labels else f"$u_{{{k}}}$"
        out.append(f"\\node[{style}] (g{k}) at ({x:.2f},{yg:.2f}) {{{lab}}};")
    for o, name in zip(outputs, out_names):
        out.append(f"\\node[sig,anchor=west] at ({x_end + 0.05:.2f},{y[o]:.2f}) {{${name}$}};")
    return "\n".join(out)

HEAD = ("\\begin{tikzpicture}[x=1cm,y=1cm,rail/.style={line width=0.5pt,color=black!70},tap/.style={line width=0.5pt},"
        "gate/.style={draw,circle,fill=orange!15,minimum size=4.4mm,inner sep=0pt,font=\\scriptsize},"
        "cell/.style={draw,rounded corners=1.5pt,fill=green!10,minimum width=9.5mm,minimum height=4mm,inner sep=1.2pt,font=\\scriptsize},sig/.style={font=\\scriptsize}]\n")
def emit(name, body):
    open(f"{OUT}/{name}.tex", "w").write(HEAD + body + "\n\\end{tikzpicture}\n"); print("wrote", name)

J = lambda p: json.load(open(f"{R}/{p}"))
s = J("synth/ha_sum/8431.json"); emit("tikz_sum8431", rails(s["gates"], 2, s["outputs"], ["x", "y"], [r"\hs"]))
j = J("synth/ha_joint/4066.json"); emit("tikz_joint4066", rails(j["gates"], 2, j["outputs"], ["x", "y"], [r"\hs", r"\hc"]))
c = J("synth/fa_carry/1894.json"); emit("tikz_carry1894", rails(c["gates"], 3, c["outputs"], ["a", "b", "c"], [r"c_{\mathrm{out}}"]))
f = J("synth/fa_joint/6640.json"); emit("tikz_fa6640", rails(f["gates"], 3, f["outputs"], ["a", "b", "c"], ["s", r"c_{\mathrm{out}}"]))
lc = J("libcost/8431.json")["costs"]["lin2011"]; cells = lc["circuit"]   # cheapest circuit found in the clean batch (72 T, lin2011 counts)
emit("tikz_cells8431", rails(cells, 2, [f"g{len(cells)-1}"], ["x", "y"], [r"g_{8431}(x,y)"], style="cell", labels=[c[0] for c in cells], dx=1.25, dy=0.42))
S10 = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/spectrum_S10.csv"))}
sm = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_summary.csv"))}
reps = sorted(g for g, r in S10.items() if r["diameter"] == "7" and sm[g]["canon12"] == str(g))
rows = [f"$g_{{{g}}}$ & {float(S10[g]['mean_size_reached']):.3f} & {S10[g]['half_size']} & {S10[g]['h_sum']} & {S10[g]['h_carry']} & {S10[g]['mul']}\\\\" for g in reps]
open(f"{OUT}/tab_delta7.tex", "w").write("\n".join(rows) + "\n"); print("wrote tab_delta7", len(reps))
