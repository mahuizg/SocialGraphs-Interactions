"""Three figures for the paper, drawn from the saved results (run r1, r2, r3 first).
Every figure shows the measured value next to its null or interval. Women = orange, men = blue;
grey = what gender-shuffled data gives. PNG (200 dpi) and PDF are written to figures/.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import COL, FIG, RES

INK, MUTED, NULLC, GRID = "#111827", "#6B7280", "#D1D5DB", "#E5E7EB"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "legend.frameon": False, "figure.dpi": 110})


def J(name):
    return json.loads((RES / name).read_text())


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def fig1():
    r = J("rq1_embeddedness_runs1000.json")
    d = pd.read_csv(RES / "rq1_comparison_set.csv")
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw={"width_ratios": [1.0, 0.8, 0.9]})

    # A: mean in-degree by citation quintile, bootstrap 95% CI
    rng = np.random.default_rng(0)
    for g, lab, off in (("male", "Men", -0.06), ("female", "Women", 0.06)):
        m, lo, hi = [], [], []
        for q in range(5):
            v = d[(d.gender == g) & (d.cit_bin == q)].in_degree.to_numpy()
            bs = rng.choice(v, (2000, len(v))).mean(1)
            m.append(v.mean()); lo.append(np.percentile(bs, 2.5)); hi.append(np.percentile(bs, 97.5))
        x = np.arange(5) + off
        a.vlines(x, lo, hi, color=COL[g], lw=1.4)
        a.plot(x, m, "-o", color=COL[g], lw=2, ms=6, mec="white", mew=1, label=f"{lab} (n = {int((d.gender == g).sum()):,})")
        a.annotate(lab, (x[-1], m[-1]), xytext=(8, 0), textcoords="offset points", va="center", color=INK)
    a.set_xticks(range(5), ["Q1\nleast cited", "Q2", "Q3", "Q4", "Q5\nmost cited"])
    a.set_xlim(-0.3, 4.9)
    a.set_ylim(0)
    a.set_ylabel("Links received from other scientists' pages\n(mean in-degree, bars = 95% bootstrap interval)")
    a.set_xlabel("Citation quintile (OpenAlex)")
    a.set_title("A  At every citation level, women's pages\n    receive fewer links")
    a.grid(axis="y", color=GRID, lw=0.6)

    # B: observed / expected under gender shuffle
    P = r["permutation_field_decade_citation5"]
    rows = [("in_degree", "Links received\n(in-degree)"), ("out_degree", "Links given\n(out-degree)"),
            ("reciprocal", "Reciprocal links"), ("zero_in", "Share with no\nincoming link"),
            ("isolate", "Share with no link\nin or out (isolates)")]
    for i, (k, lab) in enumerate(rows):
        lo, hi = P[k]["ratio_null_ci95"]
        b.plot([lo, hi], [i, i], color=NULLC, lw=10, solid_capstyle="butt")
        v = P[k]["ratio_obs_over_null"]
        b.plot(v, i, "o", color=COL["female"], ms=8, mec="white", mew=1)
        b.text(1.5, i, f"{v:.2f}  (z = {P[k]['z']:+.1f})", va="center", ha="left", color=INK, fontsize=8.5,
               clip_on=False)
    b.axvline(1, color=MUTED, lw=0.8, ls=":")
    b.set_yticks(range(len(rows)), [l for _, l in rows])
    b.invert_yaxis()
    b.set_xlim(0.55, 1.45)
    b.set_xlabel("Women's pages: observed / expected if gender were\nshuffled within field × birth decade × citation quintile")
    b.set_title("B  Less embedded in both directions\n    (grey = 95% of 1,000 shuffles)")
    b.tick_params(axis="y", length=0)
    b.spines["left"].set_visible(False)

    # C: forest of in-degree rate ratios
    M, L, F = r["models_in_degree"], r["ladder_in_degree_negbin"], r["field_by_gender"]["by_field"]
    items = [("Count models, links received", None),
             ("Negative binomial (headline)", (M["negative_binomial"]["irr"], *M["negative_binomial"]["ci95"])),
             ("Poisson, robust SE", (M["poisson_robust"]["irr"], *M["poisson_robust"]["ci95"])),
             ("Hurdle: links, given at least one", (M["hurdle"]["count_given_any_rate_ratio"], *M["hurdle"]["count_given_any_ci95"])),
             ("Prose-only links", (r["models_in_degree_prose"]["negative_binomial"]["irr"], *r["models_in_degree_prose"]["negative_binomial"]["ci95"])),
             ("Adding controls", None)] + \
            [(x["spec"], (x["irr"], *x["ci95"])) for x in L[1:5]] + \
            [("One model, field × gender (3-field network)", None)] + \
            [(f"{f.capitalize()} (n = {F[f]['n']:,})", (F[f]["irr"], *F[f]["ci95"])) for f in ("physics", "chemistry", "biology")]
    y = 0
    ticks, labs = [], []
    for lab, v in items:
        if v is None:
            c.text(-0.02, y, lab, transform=c.get_yaxis_transform(), ha="right", va="center", fontweight="bold", color=INK, fontsize=8.5)
        else:
            c.plot([v[1], v[2]], [y, y], color=COL["female"], lw=1.6)
            c.plot(v[0], y, "o", color=COL["female"], ms=6.5, mec="white", mew=1)
            c.text(1.07, y, f"{v[0]:.2f} [{v[1]:.2f}, {v[2]:.2f}]", va="center", fontsize=8, color=INK)
            ticks.append(y); labs.append(lab)
        y += 1
    c.axvline(1, color=MUTED, lw=0.8, ls=":")
    c.set_yticks(ticks, labs, fontsize=8.5)
    c.set_ylim(y - 0.5, -1.0)
    c.set_xlim(0.3, 1.45)
    c.set_xlabel("Incidence-rate ratio, women / men (1 = no gap), 95% CI")
    c.set_title("C  About 40% fewer links at equal citations,\n    in every field", x=-0.75, pad=12)
    c.tick_params(axis="y", length=0)
    c.spines["left"].set_visible(False)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig1_embeddedness")


def fig2():
    r = J("rq2_text_perms200.json")
    null = np.load(RES / "rq2_null_draws.npy")
    fw = pd.read_csv(RES / "rq2_words.csv")
    c = r["classifier_strict_masking"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1, 1.35]})
    a.hist(null[:, 1], bins=25, color=NULLC, label=f"Gender shuffled within field × decade\n({len(null)} repeats of the full cross-validation)")
    obs = c["within_field_decade_auc"]["observed"]
    a.axvline(obs, color=COL["female"], lw=2.5)
    a.text(obs - 0.008, a.get_ylim()[1] * 0.6, f"Observed\nAUC = {obs:.2f}", ha="right", va="top", color=INK, fontweight="bold")
    a.axvline(0.5, color=MUTED, lw=0.8, ls=":")
    a.text(0.502, a.get_ylim()[1] * 0.55, "chance", color=MUTED, fontsize=8, rotation=90, va="center")
    a.set_xlim(0.44, 0.9)
    a.set_xlabel("Cross-validated AUC, comparing only women and men\nof the same field and birth decade")
    a.set_ylabel("Shuffled runs")
    a.legend(loc="upper left", bbox_to_anchor=(0.2, 1.0), fontsize=8)
    a.set_title("A  With names, pronouns and gender words masked,\n    the text still tells women's pages from men's")

    top = pd.concat([fw.nlargest(18, "z_within_field_decade"), fw.nsmallest(18, "z_within_field_decade")]).sort_values("z_within_field_decade")
    yy = np.arange(len(top))
    b.barh(yy, top.z_within_field_decade, color=[COL["female"] if z > 0 else COL["male"] for z in top.z_within_field_decade], height=0.72)
    b.plot(top.z_pooled, yy, "|", color=INK, ms=9, mew=1.3, label="Without the birth-decade adjustment")
    for yi, (w, z) in enumerate(zip(top.word, top.z_within_field_decade)):
        b.text(-0.25 if z > 0 else 0.25, yi, w, ha="right" if z > 0 else "left", va="center", fontsize=8.5, color=INK)
    b.axvline(0, color=MUTED, lw=0.8)
    b.set_yticks([])
    b.spines["left"].set_visible(False)
    b.set_xlabel("Log-odds z-score that a page uses the word, combined within field × birth decade\n"
                 "← more typical of men's pages          more typical of women's pages →")
    b.legend(loc="lower right", fontsize=8)
    b.set_title("B  Women's pages: training and career steps. Men's pages: the work and its standing.\n"
                "    The pattern holds inside birth decades")
    fig.tight_layout(w_pad=2)
    save(fig, "fig2_text")


def fig3():
    r = J("rq3_homophily_runs1000.json")
    null = np.load(RES / "rq3_null_draws.npy")
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.4), gridspec_kw={"width_ratios": [1.25, 1]})
    bins = np.linspace(0.08, 0.24, 60)
    a.hist(null[0], bins=bins, color=NULLC, label="Shuffle within field × decade (original null)")
    a.hist(null[1], bins=bins, color=MUTED, alpha=0.75, label="Shuffle within link community × decade (revised null)")
    obs = r["observed_share_from_women"]
    a.axvline(obs, color=COL["female"], lw=2.5)
    a.text(obs - 0.003, a.get_ylim()[1] * 0.95, f"Observed\n{obs:.1%}", ha="right", va="top", fontweight="bold", color=INK)
    a.set_xlabel("Share of the links to women's pages that come from women's pages")
    a.set_ylabel("Shuffled runs (of 1,000)")
    a.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    a.legend(loc="upper left", fontsize=8)
    a.set_title("A  Women's pages are linked from women's pages more than\n    topic clusters and cohort can account for")

    t = pd.DataFrame(r["communities_seed0_ge100"]).sort_values("share_women")
    yy = np.arange(len(t))
    b.hlines(yy, 0, t.share_women, color=NULLC, lw=1.2)
    b.scatter(t.share_women, yy, s=18 + t["size"] / 6, color=COL["female"], edgecolor="white", linewidth=1, zorder=3)
    b.set_yticks(yy, [f"{h} (n = {n})" for h, n in zip(t.hub, t["size"])], fontsize=8)
    overall = (t.share_women * t["size"]).sum() / t["size"].sum()
    b.axvline(overall, color=MUTED, lw=0.8, ls=":")
    b.text(overall + 0.002, len(t) - 0.4, f"all: {overall:.0%}", color=MUTED, fontsize=8, va="top")
    b.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    b.set_xlim(0, 0.2)
    b.set_xticks([0, 0.05, 0.10, 0.15, 0.20])
    b.set_xlabel("Share of women in the community (label = most central page)")
    b.tick_params(axis="y", length=0)
    b.spines["left"].set_visible(False)
    b.set_title(f"B  Women are {t.share_women.min():.0%} to {t.share_women.max():.0%} of the {len(t)} largest\n    link communities: present everywhere, unevenly")
    fig.tight_layout(w_pad=2)
    save(fig, "fig3_homophily")


if __name__ == "__main__":
    fig1(); fig2(); fig3()
    print("figures written to", FIG)
