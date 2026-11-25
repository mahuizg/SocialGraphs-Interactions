"""One-panel-per-file versions of the three paper figures for the two-column PNAS template.
Small panels are drawn 7 cm wide (= 0.8 x one 8.7 cm column) for
\\begin{figure} ... width=.8\\linewidth; all panels sit inside one column. Fonts are then printed at their real size.

Same data and same encoding as figures.py (women = orange, men = blue, grey = gender-shuffled
data); panel titles are left out because the LaTeX captions carry them.
Writes PNG (300 dpi) and PDF to figures/split/. Run r1, r2, r3 first.

    fig1a_quintiles      RQ1  mean in-degree by citation quintile
    fig1b_shuffle        RQ1  observed / expected under within-stratum gender shuffle
    fig1c_models         RQ1  rate ratios from count models and robustness checks
    fig2a_auc            RQ2  within-stratum AUC vs shuffled runs
    fig2b_words          RQ2  most distinguishing words
    fig3a_homophily      RQ3  share of links to women from women vs two nulls
    fig3b_communities    RQ3  share of women per large link community
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import COL, FIG, RES

OUT = FIG / "split"
OUT.mkdir(exist_ok=True)
W = 0.8 * 8.7 / 2.54  # 0.8 of one PNAS column, inches

INK, MUTED, NULLC, GRID = "#111827", "#6B7280", "#D1D5DB", "#E5E7EB"
plt.rcParams.update({"font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                     "legend.fontsize": 6.5, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "legend.frameon": False, "pdf.fonttype": 42})


def J(name):
    return json.loads((RES / name).read_text())


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# ------------------------------------------------------------------ RQ1
def fig1a():
    d = pd.read_csv(RES / "rq1_comparison_set.csv")
    fig, a = plt.subplots(figsize=(W, 1.85), layout="constrained")
    rng = np.random.default_rng(0)
    for g, lab, off in (("male", "Men", -0.07), ("female", "Women", 0.07)):
        m, lo, hi = [], [], []
        for q in range(5):
            v = d[(d.gender == g) & (d.cit_bin == q)].in_degree.to_numpy()
            bs = rng.choice(v, (2000, len(v))).mean(1)
            m.append(v.mean()); lo.append(np.percentile(bs, 2.5)); hi.append(np.percentile(bs, 97.5))
        x = np.arange(5) + off
        a.vlines(x, lo, hi, color=COL[g], lw=1.1)
        a.plot(x, m, "-o", color=COL[g], lw=1.5, ms=4, mec="white", mew=0.7)
        a.annotate(f"{lab}\n(n = {int((d.gender == g).sum()):,})", (x[-1], m[-1]), xytext=(6, 0),
                   textcoords="offset points", va="center", color=COL[g], fontsize=6.5)
    a.set_xticks(range(5), ["Q1\nleast", "Q2", "Q3", "Q4", "Q5\nmost"])
    a.set_xlim(-0.3, 5.3)
    a.set_ylim(0)
    a.set_ylabel("Mean links received\nfrom scientists' pages")
    a.set_xlabel("Citation quintile (OpenAlex)")
    a.grid(axis="y", color=GRID, lw=0.5)
    save(fig, "fig1a_quintiles")


def fig1b():
    P = J("rq1_embeddedness_runs1000.json")["permutation_field_decade_citation5"]
    rows = [("in_degree", "Links received"), ("out_degree", "Links given"), ("reciprocal", "Reciprocal links"),
            ("zero_in", "No incoming link"), ("isolate", "Isolate (no link)")]
    fig, b = plt.subplots(figsize=(W, 1.95), layout="constrained")
    for i, (k, lab) in enumerate(rows):
        lo, hi = P[k]["ratio_null_ci95"]
        b.plot([lo, hi], [i, i], color=NULLC, lw=7, solid_capstyle="butt")
        v = P[k]["ratio_obs_over_null"]
        b.plot(v, i, "o", color=COL["female"], ms=5, mec="white", mew=0.7)
        b.text(1.47, i, f"{v:.2f}\nz = {P[k]['z']:+.1f}".replace("-", "\u2212"), va="center", ha="left", color=INK, fontsize=6, linespacing=1.0)
    b.axvline(1, color=MUTED, lw=0.6, ls=":")
    b.set_yticks(range(len(rows)), [l for _, l in rows])
    b.invert_yaxis()
    b.set_xlim(0.55, 1.45)
    b.set_xticks([0.6, 0.8, 1.0, 1.2, 1.4])
    b.set_xlabel("Women's pages: observed / expected\nunder gender shuffle")
    b.tick_params(axis="y", length=0)
    b.spines["left"].set_visible(False)
    save(fig, "fig1b_shuffle")


def fig1c():
    r = J("rq1_embeddedness_runs1000.json")
    M, L, F = r["models_in_degree"], r["ladder_in_degree_negbin"], r["field_by_gender"]["by_field"]
    items = [("Count models", None),
             ("Negative binomial", (M["negative_binomial"]["irr"], *M["negative_binomial"]["ci95"])),
             ("Poisson, robust SE", (M["poisson_robust"]["irr"], *M["poisson_robust"]["ci95"])),
             ("Hurdle, given ≥ 1 link", (M["hurdle"]["count_given_any_rate_ratio"], *M["hurdle"]["count_given_any_ci95"])),
             ("Prose-only links", (r["models_in_degree_prose"]["negative_binomial"]["irr"],
                                   *r["models_in_degree_prose"]["negative_binomial"]["ci95"])),
             ("Controls added", None)] + \
            [(x["spec"].replace(" to scientists", "").replace(" (OpenAlex)", "").replace("page length (log words)", "page length"), (x["irr"], *x["ci95"])) for x in L[1:5]] + \
            [("Field × gender, one model", None)] + \
            [(f"{f.capitalize()} (n = {F[f]['n']:,})", (F[f]["irr"], *F[f]["ci95"])) for f in ("physics", "chemistry", "biology")]
    fig, c = plt.subplots(figsize=(W, 2.55), layout="constrained")
    ticks, labs, y = [], [], 0
    for lab, v in items:
        if v is None:
            ticks.append(y); labs.append(lab)
        else:
            c.plot([v[1], v[2]], [y, y], color=COL["female"], lw=1.2)
            c.plot(v[0], y, "o", color=COL["female"], ms=4, mec="white", mew=0.7)
            ticks.append(y); labs.append(lab)
        y += 1
    c.axvline(1, color=MUTED, lw=0.6, ls=":")
    c.set_yticks(ticks, labs)
    for t, (_, v) in zip(c.get_yticklabels(), items):
        if v is None:
            t.set_fontweight("bold"); t.set_color(INK)
    c.set_ylim(y - 0.5, -0.5)
    c.set_xlim(0.3, 1.1)
    c.set_xticks([0.4, 0.6, 0.8, 1.0])
    c.set_xlabel("Rate ratio, women / men, 95% CI")
    c.tick_params(axis="y", length=0)
    c.spines["left"].set_visible(False)
    c.grid(axis="x", color=GRID, lw=0.5)
    save(fig, "fig1c_models")


# ------------------------------------------------------------------ RQ2
def fig2a():
    c = J("rq2_text_perms200.json")["classifier_strict_masking"]
    null = np.load(RES / "rq2_null_draws.npy")
    fig, a = plt.subplots(figsize=(W, 1.6), layout="constrained")
    a.hist(null[:, 1], bins=25, color=NULLC, label=f"Shuffled within\nfield \u00d7 decade\n({len(null)} runs)")
    obs = c["within_field_decade_auc"]["observed"]
    a.axvline(obs, color=COL["female"], lw=1.8)
    a.text(obs - 0.008, a.get_ylim()[1] * 0.55, f"Observed\nAUC = {obs:.2f}", ha="right", va="top",
           color=INK, fontweight="bold", fontsize=6.5)
    a.axvline(0.5, color=MUTED, lw=0.6, ls=":")
    a.set_xlim(0.44, 0.9)
    a.set_xlabel("Cross-validated AUC, women vs men\nof the same field and birth decade")
    a.set_ylabel("Shuffled runs")
    a.legend(loc="upper left", bbox_to_anchor=(0.28, 1.0))
    save(fig, "fig2a_auc")


def fig2b():
    fw = pd.read_csv(RES / "rq2_words.csv")
    k = 16
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.75), layout="constrained", sharex=False)
    sets = (("female", "Women's pages", fw.nlargest(k, "z_within_field_decade"), 1),
            ("male", "Men's pages", fw.nsmallest(k, "z_within_field_decade"), -1))
    for ax, (g, title, top, sign) in zip(axes, sets):
        yy = np.arange(len(top))
        ax.barh(yy, sign * top.z_within_field_decade, color=COL[g], height=0.7)
        ax.plot(sign * top.z_pooled, yy, "|", color=INK, ms=5, mew=0.8,
                label="Without decade adjustment" if g == "female" else None)
        ax.set_yticks(yy, top.word)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(0, 11.5 if g == "female" else 6.5)
        ax.set_xticks([0, 5, 10] if g == "female" else [0, 2, 4, 6])
        ax.set_title(title, fontsize=7, color=COL[g], loc="left", fontweight="bold")
        ax.set_xlabel("|z-score|")
        ax.grid(axis="x", color=GRID, lw=0.5)
        ax.set_axisbelow(True)

    save(fig, "fig2b_words")


# ------------------------------------------------------------------ RQ3
def fig3a():
    r = J("rq3_homophily_runs1000.json")
    null = np.load(RES / "rq3_null_draws.npy")
    fig, a = plt.subplots(figsize=(W, 1.75), layout="constrained")
    bins = np.linspace(0.08, 0.24, 50)
    a.hist(null[0], bins=bins, color=NULLC, label="Shuffle within field × decade")
    a.hist(null[1], bins=bins, color=MUTED, alpha=0.75, label="Shuffle within link community × decade")
    obs = r["observed_share_from_women"]
    a.axvline(obs, color=COL["female"], lw=1.8)
    a.text(obs - 0.003, a.get_ylim()[1] * 0.62, f"Observed\n{obs:.1%}", ha="right", va="top",
           fontweight="bold", color=INK, fontsize=6.5)
    a.set_xlabel("Share of links to women's pages\nthat come from women's pages")
    a.set_ylabel("Shuffled runs")
    a.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    a.set_xticks([0.08, 0.12, 0.16, 0.20, 0.24])
    a.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, borderaxespad=0.2)
    save(fig, "fig3a_homophily")


def fig3b():
    r = J("rq3_homophily_runs1000.json")
    t = pd.DataFrame(r["communities_seed0_ge100"]).sort_values("share_women")
    yy = np.arange(len(t))
    fig, b = plt.subplots(figsize=(W, 2.5), layout="constrained")
    b.hlines(yy, 0, t.share_women, color=NULLC, lw=0.9)
    b.scatter(t.share_women, yy, s=8 + t["size"] / 10, color=COL["female"], edgecolor="white", linewidth=0.6, zorder=3)
    b.set_yticks(yy, [f"{h} (n = {n})" for h, n in zip(t.hub, t["size"])], fontsize=6)
    overall = (t.share_women * t["size"]).sum() / t["size"].sum()
    b.axvline(overall, color=MUTED, lw=0.6, ls=":")
    b.text(overall + 0.002, -0.6, f"all: {overall:.0%}", color=MUTED, fontsize=6.5, va="bottom")
    b.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    b.set_xlim(0, 0.2)
    b.set_ylim(-0.8, len(t) - 0.4)
    b.set_xticks([0, 0.05, 0.10, 0.15, 0.20])
    b.set_xlabel("Share of women in the community")
    b.set_xlabel("Share of women in the link community")
    b.tick_params(axis="y", length=0)
    b.spines["left"].set_visible(False)
    save(fig, "fig3b_communities")


if __name__ == "__main__":
    for f in (fig1a, fig1b, fig1c, fig2a, fig2b, fig3a, fig3b):
        f()
    print("figures written to", OUT)
