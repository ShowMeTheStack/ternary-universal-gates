#!/usr/bin/env python3
"""Figures for the paper, from FRESH results only (results/, never *_pre_batch_*).
Dataviz method: one sequential blue ramp for magnitude, categorical slots blue/orange/aqua,
thin marks, recessive grid, text in text tokens. Every series is identified by a framed legend
placed in an empty region of the axes (never by text laid over the marks).
Run:  /usr/bin/python3 eval/make_figures.py [results_dir] [paper/figs]
"""
import csv, json, glob, os, sys, collections, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

R = sys.argv[1] if len(sys.argv) > 1 else "results"
OUT = sys.argv[2] if len(sys.argv) > 2 else "paper/figs"
os.makedirs(OUT, exist_ok=True)
assert "pre_batch" not in os.path.abspath(R)

TXT, TXT2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a897f", "#e6e5e0", "#ffffff"
BLUE, ORANGE, AQUA, LIGHTBLUE = "#2a78d6", "#eb6834", "#1baf7a", "#b7d3f6"
RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("blue_seq", RAMP)
plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 8, "axes.titlesize": 8.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "legend.fontsize": 6.5, "text.color": TXT, "axes.labelcolor": TXT, "xtick.color": TXT2, "ytick.color": TXT2,
                     "axes.edgecolor": GRID, "axes.linewidth": 0.6, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "pdf.fonttype": 42, "font.family": "sans-serif"})
W = 3.45  # IEEE/Elsevier column width in inches

def style(ax, grid="y"):
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(length=2, width=0.5)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.5); ax.set_axisbelow(True)

def legend(ax, handles=None, labels=None, loc="best", **kw):
    opts = dict(loc=loc, frameon=True, framealpha=1.0, facecolor=SURF, edgecolor=GRID, borderpad=0.5, labelspacing=0.35, handlelength=1.8)
    opts.update(kw)
    lg = ax.legend(handles, labels, **opts) if handles else ax.legend(**opts)
    lg.get_frame().set_linewidth(0.5)
    return lg

def save(fig, name):
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight", pad_inches=0.02, dpi=200)
    plt.close(fig); print("wrote", name)

ha = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_ha.csv"))}
sm = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/synth_summary.csv"))}
assert len(ha) == 3774 == len(sm)

# ---------------------------------------------------------------- 1. depth heat map
def fig_depth_heatmap():
    cnt = collections.Counter((int(r["Ds"]), int(r["Dc"])) for r in ha.values())
    xs = list(range(2, 8)); ys = list(range(3, 8))
    M = np.array([[cnt.get((x, y), 0) for x in xs] for y in ys], dtype=float)
    fig, ax = plt.subplots(figsize=(W, W * 0.78))
    ax.imshow(np.where(M > 0, np.log10(M + 1), np.nan), cmap=CMAP, origin="lower", aspect="auto", vmin=0, vmax=np.log10(M.max() + 1))
    ax.set_xticks(range(len(xs))); ax.set_xticklabels(xs); ax.set_yticks(range(len(ys))); ax.set_yticklabels(ys)
    ax.set_xlabel(r"minimum depth of $h_{\mathrm{sum}}$"); ax.set_ylabel(r"minimum depth of $h_{\mathrm{carry}}$")
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            v = cnt.get((x, y), 0)
            if v: ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=6.5, color=(SURF if v > 300 else TXT))
    ax.set_xticks(np.arange(-.5, len(xs), 1), minor=True); ax.set_yticks(np.arange(-.5, len(ys), 1), minor=True)
    ax.grid(which="minor", color=SURF, linewidth=1.2); ax.tick_params(which="minor", length=0)
    for s in ax.spines.values(): s.set_visible(False)
    # label the lone cell in the empty cell directly above it (no arrow across cells)
    ax.text(0, 2, "class of\n$g_{8431}$\n$\\downarrow$", ha="center", va="center", fontsize=5.6, color=TXT2, linespacing=1.1)
    save(fig, "fig_depth_heatmap")

# ---------------------------------------------------------------- 2. exact size scatter
def fig_size_scatter():
    pts = collections.Counter((int(r["ha_sum_size"]), int(r["ha_carry_size"])) for r in sm.values()
                              if r["ha_sum_status"] == "OPTIMAL" and r["ha_carry_status"] == "OPTIMAL")
    n = sum(pts.values())
    fig, ax = plt.subplots(figsize=(W, W * 0.82)); style(ax, grid="both")
    xs, ys, ss = zip(*[(x, y, c) for (x, y), c in pts.items()])
    sc = ax.scatter(xs, ys, s=np.array(ss) * 0.55, color=BLUE, alpha=0.75, linewidths=0.6, edgecolors=SURF, zorder=3)
    for (x, y), c in pts.items():
        if c >= 60: ax.text(x, y, f"{c}", ha="center", va="center", fontsize=5.5, color=SURF if c > 250 else TXT, zorder=4)
    # the line S_s + S_c = 8 drawn only where no bubble sits on it (segments between the two optima)
    ax.plot([1.5, 5.6], [6.5, 2.4], color=ORANGE, lw=0.9, ls=(0, (3, 2)), zorder=2)
    ax.annotate(r"$g_{8431}$ class", xy=(2.08, 6.0), xytext=(3.2, 6.6), fontsize=6.5, ha="left", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=TXT2, shrinkB=2), zorder=5)
    ax.annotate(r"$g_{6640}$ class", xy=(3.93, 3.92), xytext=(2.0, 3.0), fontsize=6.5, ha="left", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=TXT2, shrinkB=2), zorder=5)
    ax.set_xlim(1.4, 10.6); ax.set_ylim(2.4, 10.6); ax.set_xticks(range(2, 11)); ax.set_yticks(range(3, 11))
    ax.set_xlabel(r"exact DAG size of $h_{\mathrm{sum}}$"); ax.set_ylabel(r"exact DAG size of $h_{\mathrm{carry}}$")
    h = [Line2D([], [], marker="o", color=BLUE, lw=0, ms=6, alpha=0.75), Line2D([], [], color=ORANGE, lw=0.9, ls=(0, (3, 2)))]
    legend(ax, h, [f"gates with both sizes proven ({n:,});\narea ∝ number of gates", r"$S_s+S_c=8$ (two classes)"], loc="upper left")
    save(fig, "fig_size_scatter")

# ---------------------------------------------------------------- 3. joint HA and MUL histograms
def fig_joint_mul_hist():
    joint = collections.Counter(int(r["ha_joint_size"]) for r in sm.values() if r["ha_joint_status"] == "OPTIMAL")
    jub = collections.Counter(int(r["ha_joint_size"]) for r in sm.values() if r["ha_joint_status"] != "OPTIMAL" and r["ha_joint_size"])
    mul = collections.Counter(int(r["mul_size"]) for r in sm.values())
    fig, axs = plt.subplots(1, 2, figsize=(W, W * 0.62), gridspec_kw=dict(wspace=0.45, width_ratios=[1.35, 1]))
    for ax, (title, cnt, extra) in zip(axs, [("joint half adder", joint, jub), ("trit multiplier", mul, None)]):
        style(ax)
        ks = sorted(set(cnt) | set(extra or {}))
        ax.bar(ks, [cnt.get(k, 0) for k in ks], width=0.78, color=BLUE, zorder=3)
        if extra: ax.bar(ks, [extra.get(k, 0) for k in ks], bottom=[cnt.get(k, 0) for k in ks], width=0.78, color=LIGHTBLUE, zorder=3)
        tot = {k: cnt.get(k, 0) + (extra.get(k, 0) if extra else 0) for k in ks}
        for k in ks:
            if tot[k]: ax.text(k, tot[k] + 14, f"{tot[k]}", ha="center", va="bottom", fontsize=4.8, color=TXT2, rotation=90 if len(ks) > 10 else 0)
        ax.set_xticks(ks); ax.tick_params(axis="x", labelsize=5.6, rotation=90); ax.set_title(title, loc="left")
        ax.set_ylim(0, max(tot.values()) * (1.6 if extra else 1.25))
    axs[0].set_ylabel("universal gates"); fig.supxlabel("minimum DAG size", fontsize=8, y=-0.02)
    legend(axs[0], [Patch(color=BLUE), Patch(color=LIGHTBLUE)], ["proven optimal", "upper bound only"], loc="upper right", fontsize=5.6, handlelength=1.2)
    save(fig, "fig_joint_mul_hist")

# ---------------------------------------------------------------- 4. E14 spectrum
def fig_spectrum():
    S9 = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/spectrum_S9.csv"))}
    S10 = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/spectrum_S10.csv"))}
    H = np.array([list(map(int, r["hist"].split())) for r in S9.values()])
    C = np.cumsum(H, axis=1) / 19683.0; s = np.arange(C.shape[1])
    c12 = collections.defaultdict(list)
    for g, r in sm.items(): c12[r["canon12"]].append(g)
    diam_rep = {sm[g]["canon12"]: (int(r["diameter"]) if r["diameter"] else 11) for g, r in S10.items()}
    per_gate = collections.Counter()
    for c, gs in c12.items():
        d = diam_rep.get(c)
        if d is None: d = {int(S9[g]["diameter"]) for g in gs if S9[g]["diameter"]}.pop()
        per_gate[d] += len(gs)
    fig, axs = plt.subplots(1, 2, figsize=(W, W * 0.62), gridspec_kw=dict(width_ratios=[1.5, 1], wspace=0.5))
    ax = axs[0]; style(ax, grid="y")
    lo, hi = np.percentile(C, 10, axis=0), np.percentile(C, 90, axis=0)
    ax.fill_between(s, lo, hi, color="#cde2fb", lw=0, zorder=2)
    ax.plot(s, np.median(C, axis=0), color=BLUE, lw=1.6, zorder=4)
    g1 = np.cumsum(list(map(int, S9[8431]["hist"].split()))) / 19683.0; ax.plot(s, g1, color=ORANGE, lw=1.2, zorder=4)
    worst = min(S9.values(), key=lambda r: int(r["reached"]))
    g2 = np.cumsum(list(map(int, worst["hist"].split()))) / 19683.0; ax.plot(s, g2, color=AQUA, lw=1.2, zorder=4)
    ax.set_xlabel("size $s$ (gate instances)"); ax.set_ylabel("fraction of functions realised\nwith $\\leq s$ instances")
    ax.set_xticks(range(0, 10)); ax.set_ylim(0, 1.02); ax.set_yticks([0, .25, .5, .75, 1])
    h = [Line2D([], [], color=ORANGE, lw=1.2), Line2D([], [], color=BLUE, lw=1.6), Patch(color="#cde2fb"), Line2D([], [], color=AQUA, lw=1.2)]
    legend(ax, h, [r"$g_{8431}$", "median gate", "10th–90th pct.", f"slowest ($g_{{{worst['gate']}}}$)"], loc="upper left", fontsize=5.4, handlelength=1.2, borderpad=0.35)
    ax = axs[1]; style(ax, grid="y")
    ks = [7, 8, 9, 10, 11]; vals = [per_gate.get(k, 0) for k in ks]
    ax.bar(range(len(ks)), vals, width=0.78, color=BLUE, zorder=3)
    for i, v in enumerate(vals): ax.text(i, v + 20, f"{v:,}", ha="center", va="bottom", fontsize=5.4, color=TXT2)
    ax.set_xticks(range(len(ks))); ax.set_xticklabels(["7", "8", "9", "10", "≥11"]); ax.tick_params(axis="x", labelsize=6)
    ax.set_xlabel("size-diameter $\\Delta$"); ax.set_ylabel("universal gates"); ax.set_ylim(0, max(vals) * 1.2)
    save(fig, "fig_spectrum")

# ---------------------------------------------------------------- 5. E7 library cost of the universal gates
def fig_libcost():
    rows = [json.load(open(f)) for f in glob.glob(f"{R}/libcost/*.json")]; assert len(rows) == 966
    T = json.load(open(f"{R}/libcost_targets.json"))
    cost = collections.Counter(r["costs"]["lin2011"]["transistors"] for r in rows)
    fig, ax = plt.subplots(figsize=(W, W * 0.7)); style(ax)
    ks = sorted(cost); ax.bar(ks, [cost[k] for k in ks], width=1.6, color=BLUE, zorder=3)
    top = max(cost.values())
    ylo, yhi = top * 1.12, top * 1.34
    refs = [("mul", r"$\mu$ 36 T", "right"), ("h_carry", r"$h_{\mathrm{carry}}$ 40 T", "left"), ("h_sum", r"$h_{\mathrm{sum}}$ 70 T", "right"), ("ha_joint", "joint HA 84 T", "left")]
    for name, lab, ha_ in refs:
        x = T[name]["lin2011"]["transistors"]
        ax.plot([x, x], [0, ylo], color=ORANGE, lw=0.9, ls=(0, (3, 2)), zorder=2, clip_on=False)
        ax.text(x + (0.6 if ha_ == "left" else -0.6), ylo, lab, color=ORANGE, fontsize=6, ha=ha_, va="center")
    ax.plot([72, 72], [0, yhi], color=AQUA, lw=0.9, ls=(0, (1, 1.5)), zorder=2, clip_on=False)
    ax.text(72, yhi + top * 0.03, "Etiemble full adder 72 T", color=AQUA, fontsize=6, ha="center", va="bottom")
    ax.set_xlabel("transistors per universal gate over $L^{**}$\n(Lin–Kim–Lombardi counts; one bar per class)")
    ax.set_ylabel(r"$Z_2\times Z_2$ classes"); ax.set_ylim(0, top * 1.05); ax.set_xlim(20, 98); ax.set_xticks(range(20, 91, 10))
    save(fig, "fig_libcost")

# ---------------------------------------------------------------- 6. Stage B full-adder bounds (per class)
def fig_fa_bounds():
    pts = collections.Counter((int(r["fa_joint_lb"]), int(r["fa_joint_size"])) for r in sm.values() if r["fa_joint_size"])
    n = sum(pts.values())
    fig, ax = plt.subplots(figsize=(W, W * 0.78)); style(ax, grid="both")
    xs, ys, ss = zip(*[(x, y, c) for (x, y), c in pts.items()])
    ax.scatter(xs, ys, s=np.array(ss) * 2.2, color=BLUE, alpha=0.75, linewidths=0.6, edgecolors=SURF, zorder=3)
    ax.plot([8, 16], [8, 16], color=MUTED, lw=0.7, zorder=2)
    for g, dx, dy in ((6640, 1.2, -1.2), (8431, 0.0, -4.0), (3394, 1.3, 1.2)):
        r = sm[g]; x0, y0 = int(r["fa_joint_lb"]), int(r["fa_joint_size"])
        ax.annotate(f"$g_{{{g}}}$", xy=(x0, y0), xytext=(x0 + dx, y0 + dy), fontsize=6.5, ha="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=TXT2), zorder=5)
    ax.set_xlabel("proven lower bound (gate instances)"); ax.set_ylabel("best known circuit (upper bound)")
    ax.set_xlim(8.3, 15.7); ax.set_xticks(range(9, 16)); ax.set_ylim(6, 56)
    h = [Line2D([], [], marker="o", color=BLUE, lw=0, ms=6, alpha=0.75), Line2D([], [], color=MUTED, lw=0.7)]
    legend(ax, h, [f"two-output full adder, {n} classes;\narea ∝ number of classes", "LB = UB"], loc="upper left")
    save(fig, "fig_fa_bounds")

# ---------------------------------------------------------------- 7+. premium and cost figures
def _premium_rows():
    lc = {}
    for f in glob.glob(f"{R}/libcost/*.json"):
        j = json.load(open(f)); lc[j["gate"]] = j
    T = json.load(open(f"{R}/libcost_targets.json"))
    cHA, cM = T["ha_joint"]["lin2011"]["transistors"], T["mul"]["lin2011"]["transistors"]
    members = collections.defaultdict(list)
    for g, r in sm.items(): members[r["canon4"]].append(g)
    rows = []
    for g, j in lc.items():
        r = sm[g]; mem = members[str(g)]
        jo = [int(sm[x]["ha_joint_size"]) for x in mem if sm[x]["ha_joint_size"]]
        mu = min(int(sm[x]["mul_size"]) for x in mem)
        fa = int(r["fa_joint_size"]) if r["fa_joint_size"] else None
        costs = {v: j["costs"][v]["transistors"] for v in ("lin2011", "sharifi2015", "younepal2011")}
        c = costs["lin2011"]
        rows.append(dict(gate=g, costs=costs, P_HA=(min(jo) * c / cHA if jo else None), P_mul=mu * c / cM, P_FA=(fa * c / 72 if fa else None)))
    return rows

def _ecdf(ax, vals, color, ls="solid"):
    v = np.sort(np.array(vals, dtype=float)); y = np.arange(1, len(v) + 1) / len(v)
    ax.step(v, y, where="post", color=color, lw=1.4, ls=ls, zorder=3)
    return Line2D([], [], color=color, lw=1.4, ls=ls)

def fig_premium():
    rows = _premium_rows()
    fig, ax = plt.subplots(figsize=(W, W * 0.66)); style(ax, grid="both")
    h1 = _ecdf(ax, [r["P_HA"] for r in rows if r["P_HA"]], BLUE)
    h2 = _ecdf(ax, [r["P_mul"] for r in rows], ORANGE)
    h3 = _ecdf(ax, [r["P_FA"] for r in rows if r["P_FA"]], AQUA)
    ax.axvline(1.43, color=MUTED, lw=0.8, ls=(0, (3, 2)), zorder=2); h4 = Line2D([], [], color=MUTED, lw=0.8, ls=(0, (3, 2)))
    ax.set_xlabel("universality premium $P$"); ax.set_ylabel("fraction of the 966 classes"); ax.set_xlim(0, 38); ax.set_ylim(0, 1.02)
    ax.set_yticks([0, .25, .5, .75, 1])
    legend(ax, [h1, h2, h3, h4], ["half adder vs $L^{**}$ optimum (84 T)", "trit product vs $L^{**}$ optimum (36 T)", "full adder (best known) vs Etiemble 72 T", "binary NAND half adder: 1.43"], loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=5.6, columnspacing=1.0)
    save(fig, "fig_premium")

def fig_cost_variants():
    rows = _premium_rows()
    fig, ax = plt.subplots(figsize=(W, W * 0.64)); style(ax, grid="both")
    h1 = _ecdf(ax, [r["costs"]["younepal2011"] for r in rows], AQUA)
    h2 = _ecdf(ax, [r["costs"]["lin2011"] for r in rows], BLUE)
    h3 = _ecdf(ax, [r["costs"]["sharifi2015"] for r in rows], ORANGE)
    ax.set_xlabel("transistor cost of one universal gate over $L^{**}$"); ax.set_ylabel("fraction of the 966 classes")
    ax.set_xlim(10, 120); ax.set_ylim(0, 1.02); ax.set_yticks([0, .25, .5, .75, 1])
    legend(ax, [h1, h2, h3], ["You–Nepal cells (STI 3, NAND 5)", "Lin–Kim–Lombardi cells (STI 6, NAND 10)", "Sharifi cells (STI 8, NAND 16)"], loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=5.6, columnspacing=1.0)
    save(fig, "fig_cost_variants")

def fig_adders():
    rows = list(csv.DictReader(open(f"{R}/e8_adders.csv"))); N = [int(r["N_bits"]) for r in rows]
    fig, ax = plt.subplots(figsize=(W, W * 0.66)); style(ax, grid="y")
    hs = []
    for key, color, mk in (("tern_RCA_T_single_gate", AQUA, "s"), ("tern_RCA_T_etiemble", ORANGE, "^"), ("bin_RCA_T_cmos", BLUE, "o")):
        y = [int(r[key]) for r in rows]
        ax.plot(N, y, color=color, lw=1.4, marker=mk, ms=3.6, zorder=3); hs.append(Line2D([], [], color=color, lw=1.4, marker=mk, ms=3.6))
    ax.set_xscale("log", base=2); ax.set_yscale("log"); ax.set_xticks(N); ax.set_xticklabels([str(n) for n in N]); ax.set_ylim(30, 60000)
    ax.set_xlabel("operand width $N$ (bits; $\\lceil N/\\log_2 3\\rceil$ trits)"); ax.set_ylabel("ripple-carry adder, transistors")
    legend(ax, hs, ["ternary, single gate $g_{6640}$ (624 T per FA)", "ternary, Etiemble cells (72 T per FA)", "binary, CMOS (28 T per FA)"], loc="lower right", fontsize=5.8)
    save(fig, "fig_adders")

def fig_multipliers():
    rows = list(csv.DictReader(open(f"{R}/e9_multipliers.csv"))); x = np.arange(len(rows)); w = 0.36
    fig, ax = plt.subplots(figsize=(W, W * 0.7)); style(ax)
    u = [float(r["ratio_unbal_bin"]) for r in rows]; b = [float(r["ratio_bal_bin"]) for r in rows]
    ax.bar(x - w / 2, u, w, color=ORANGE, zorder=3); ax.bar(x + w / 2, b, w, color=BLUE, zorder=3)
    for i, (a, c) in enumerate(zip(u, b)):
        ax.text(i - w / 2, a + 0.05, f"{a:.2f}", ha="center", fontsize=5.8, color=TXT2); ax.text(i + w / 2, c + 0.05, f"{c:.2f}", ha="center", fontsize=5.8, color=TXT2)
    ax.axhline(1, color=MUTED, lw=0.8, zorder=2)
    ax.set_xticks(x); ax.set_xticklabels([f"{r['N_bits']} bits\n{r['N_trits']} trits" for r in rows]); ax.tick_params(axis="x", labelsize=6); ax.set_ylim(0, 4.0)
    ax.set_ylabel("cost / binary multiplier cost")
    legend(ax, [Patch(color=ORANGE), Patch(color=BLUE), Line2D([], [], color=MUTED, lw=0.8)], ["unbalanced ternary (product has a carry)", "balanced ternary (carry-free product)", "binary multiplier"], loc="upper left", fontsize=5.8)
    save(fig, "fig_multipliers")

def fig_spectrum_corr():
    S9 = {int(r["gate"]): r for r in csv.DictReader(open(f"{R}/spectrum_S9.csv"))}
    pts = collections.Counter()
    for g, r in S9.items():
        if r["h_sum"] != "-1": pts[(round(float(r["mean_size_reached"]), 1), int(r["h_sum"]))] += 1
    fig, ax = plt.subplots(figsize=(W, W * 0.72)); style(ax, grid="both")
    xs, ys, ss = zip(*[(x, y, c) for (x, y), c in pts.items()])
    ax.scatter(xs, ys, s=np.array(ss) * 1.2 + 2, color=BLUE, alpha=0.6, linewidths=0.4, edgecolors=SURF, zorder=3)
    for g, lab, dx, dy in ((8431, r"$g_{8431}$", 0.45, 0.0), (4066, r"$g_{4066}$", 0.0, -1.2)):
        r = S9[g]; x0, y0 = float(r["mean_size_reached"]), int(r["h_sum"])
        ax.annotate(lab, xy=(x0, y0), xytext=(x0 + dx, y0 + dy), fontsize=6.5, ha="center", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=TXT2), zorder=5)
    ax.set_xlabel("mean size of a two-input function over the gate\n(functions reached within $s=9$ instances)"); ax.set_ylabel("exact DAG size of $h_{\\mathrm{sum}}$")
    ax.set_yticks(range(2, 11)); ax.set_ylim(1.4, 10.4); ax.set_xlim(5.3, 8.3)
    legend(ax, [Line2D([], [], marker="o", color=BLUE, lw=0, ms=6, alpha=0.6)], ["3,162 gates, Spearman $\\rho=0.74$;\narea ∝ number of gates"], loc="lower right")
    save(fig, "fig_spectrum_corr")

if __name__ == "__main__":
    for f in (fig_depth_heatmap, fig_size_scatter, fig_joint_mul_hist, fig_spectrum, fig_libcost, fig_fa_bounds,
              fig_premium, fig_cost_variants, fig_adders, fig_multipliers, fig_spectrum_corr):
        f()
