"""Builds who_gets_remembered_revised.ipynb. Run:  python build_notebook.py && jupyter nbconvert --to notebook --execute --inplace who_gets_remembered_revised.ipynb"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Who Gets Remembered? Revised analysis, step by step

**Question.** At equal citations, field and birth decade, are women scientists' Wikipedia pages less embedded in the link
network between scientists' pages, and are they written differently?

This notebook walks through the revised analysis. The heavy computations live in `../src/` (run `../run_all.sh` once);
here we load the data and the saved results, look at them, and repeat small pieces so each step can be seen.
Each section says what the measurement captures, what it misses, and shows the check next to the claim.
""")
code("""
import sys, json, warnings
sys.path.insert(0, "../src"); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, networkx as nx, matplotlib.pyplot as plt
from IPython.display import Image, display
from common import *
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "figure.dpi": 110})
J = lambda n: json.loads((RES / n).read_text())
r1, r2, r3, sel = J("rq1_embeddedness_runs1000.json"), J("rq2_text_perms200.json"), J("rq3_homophily_runs1000.json"), J("selection_check.json")
""")
md("""
## 1. Data

Nodes are English Wikipedia biographies of physicists and chemists born 1920 to 1980 (Wikidata). A directed edge A → B means
A's page links to B's page. Impact comes from OpenAlex, matched only through an ORCID or OpenAlex ID stored on Wikidata.
""")
code("""
nodes = load_nodes(); main = nodes[nodes.main_field]
G = graph(main, "all"); main = add_degrees(main, G)
d = comparison_set(main)
print(f"network: {G.number_of_nodes():,} pages, {G.number_of_edges():,} links, {nx.number_of_isolates(G):,} isolated pages")
print(f"largest weakly connected component: {len(max(nx.weakly_connected_components(G), key=len)):,} pages")
print(f"comparison set (matched to OpenAlex): {len(d):,} = {d.female.sum()} women + {(1-d.female).sum():,} men")
pd.crosstab(main.gender, main.usable.map({True: "matched", False: "not matched"}), margins=True)
""")
md("""
**The network is sparse.** About one link per page, and nearly half the pages have no link at all. This matters for the
choice of measure: PageRank on such a network is close to a transformed in-degree with a large floor, and taking its logarithm
compresses differences. So the headline below is the plain count of links received.
""")
code("""
fig, ax = plt.subplots(1, 2, figsize=(10, 3.2))
for g in ("male", "female"):
    v = d[d.gender == g].in_degree.clip(upper=10).value_counts(normalize=True).sort_index()
    ax[0].plot(v.index, v.values, "-o", color=COL[g], label={"male": "Men", "female": "Women"}[g])
ax[0].set_xticks(range(11), [*map(str, range(10)), "10+"]); ax[0].set_xlabel("Links received from other scientists' pages")
ax[0].set_ylabel("Share of pages"); ax[0].legend(frameon=False); ax[0].set_title("In-degree distribution, comparison set", loc="left")
dec = d.groupby(["birth_decade", "gender"]).size().unstack().pipe(lambda t: t / t.sum())
dec.rename(columns={"female": "Women", "male": "Men"})[["Men", "Women"]].plot.bar(ax=ax[1], color=[COL["male"], COL["female"]], width=0.8)
ax[1].set_ylabel("Share of each gender"); ax[1].set_xlabel("Birth decade"); ax[1].set_title("Matched women are younger", loc="left"); ax[1].legend(frameon=False)
plt.tight_layout()
""")
md("""
## 2. RQ1: embeddedness at equal impact

**Captures:** how often other scientists' biographies point to a page, and whether the page points to others.
**Misses:** links from topic, institution and prize pages; readers; why a link exists.

First the raw numbers. They are *not* at equal impact (women in the set are younger and less cited), so they only set the scene.
""")
code("""
D = r1["descriptives_raw"]
pd.DataFrame({k: D[k] for k in ("in_degree", "out_degree", "reciprocal", "zero_in", "zero_out", "isolate")}).T.rename(
    index={"in_degree": "links received (mean)", "out_degree": "links given (mean)", "reciprocal": "reciprocal links (mean)",
           "zero_in": "share with no incoming link", "zero_out": "share with no outgoing link", "isolate": "share isolated"}).round(3)
""")
md("""
### The check: shuffle gender within strata

Keep the network fixed. Inside each cell of field × birth decade × citation quintile, shuffle who is a woman.
If women's pages received links like comparable men's, the real value would look like the shuffled ones.
Below, one small run (200 shuffles) done live; the saved run uses 1,000.
""")
code("""
rng = np.random.default_rng(1); codes = pd.factorize(d.stratum)[0]; f = d.female.to_numpy(); y = d.in_degree.to_numpy(float)
null = np.array([y[permute_within(f, codes, rng) == 1].mean() for _ in range(200)])
fig, ax = plt.subplots(figsize=(6, 2.8))
ax.hist(null, bins=25, color="#D1D5DB"); ax.axvline(y[f == 1].mean(), color=COL["female"], lw=2.5)
ax.set_xlabel("Mean links received by women's pages"); ax.set_ylabel("Shuffles")
ax.set_title(f"Observed {y[f==1].mean():.2f} vs {null.mean():.2f} expected (ratio {y[f==1].mean()/null.mean():.2f})", loc="left");
""")
code("""
rows = []
for name, key in (("field x decade x citation quintile", "permutation_field_decade_citation5"), ("subfield x decade x citation tercile", "permutation_subfield_decade_citation3")):
    for k in ("in_degree", "out_degree", "reciprocal", "zero_in", "isolate"):
        p = r1[key][k]; rows.append({"strata": name, "outcome": k, "women observed": p["observed"], "expected under shuffle": p["null_mean"], "ratio": p["ratio_obs_over_null"], "z": p["z"]})
pd.DataFrame(rows).set_index(["strata", "outcome"]).round(3)
""")
md("""
### A second method: count models

A negative binomial regression gives the size of the gap as a rate ratio with an interval. A hurdle model splits it into
"does the page get any link?" and "how many, given at least one?". Both parts show a gap.
""")
code("""
M = r1["models_in_degree"]; H = M["hurdle"]
print(f"negative binomial   women/men = {M['negative_binomial']['irr']:.2f}  CI {np.round(M['negative_binomial']['ci95'], 2)}")
print(f"Poisson, robust SE  women/men = {M['poisson_robust']['irr']:.2f}  CI {np.round(M['poisson_robust']['ci95'], 2)}")
print(f"clustered by community        = {r1['clustered_by_community']['irr']:.2f}  CI {np.round(r1['clustered_by_community']['ci95'], 2)}")
print(f"hurdle 1: any incoming link   = {H['any_link_diff_pct_points']:+.1f} points  CI {np.round(H['any_link_diff_ci95'], 1)}")
print(f"hurdle 2: links | at least 1  = {H['count_given_any_rate_ratio']:.2f}  CI {np.round(H['count_given_any_ci95'], 2)}")
print(f"old headline, log PageRank    = {r1['pagerank_supplement']['ratio_geometric']:.2f}  CI {np.round(r1['pagerank_supplement']['ci95'], 2)}")
display(Image(str(FIG / "fig1_embeddedness.png")))
""")
md("""
**Figure 1.** (A) Mean links received by citation quintile. (B) Observed value for women divided by the value expected under
shuffling; the grey bar is where 95% of shuffles fall. (C) Rate ratios from the count models, with controls added, with prose-only
links, and by field.

### What the gap runs through

Adding the page's own links to the model moves the ratio toward 1. Linking is often mutual, so this is a pathway and not an
explanation that makes the gap go away: women's pages are less woven into the network in both directions.
""")
code("""
display(pd.DataFrame(r1["ladder_in_degree_negbin"]).assign(ci=lambda t: t.ci95.map(lambda c: f"[{c[0]:.2f}, {c[1]:.2f}]"))[["spec", "irr", "ci"]].round(2))
F = r1["field_by_gender"]
display(pd.DataFrame(F["by_field"]).T[["n", "women", "irr", "ci95", "raw_isolate_share"]])
print("joint test that the gap differs by field: p =", round(F["joint_interaction_p"], 2))
pd.read_csv(RES / "rq1_robustness.csv")
""")
md("""
### Selection: who is in the comparison set?

Only pages with an ID on Wikidata can be compared at equal citations. Without a citation control we can still ask whether
the gap exists among pages that were *not* matched.
""")
code("""
display(pd.DataFrame(sel["match_rate_by_decade"]).T.round(2))
pd.DataFrame({k: {"n": v["n"], "women": v["women"], "NB rate ratio": v["negbin_irr"]["irr"], "CI low": v["negbin_irr"]["ci95"][0], "CI high": v["negbin_irr"]["ci95"][1]}
              for k, v in sel["gap_without_citation_control"].items()}).T.round(2)
""")
md("""
## 3. RQ3: who links to women's pages?

**Captures:** same-gender linking. **Misses:** the reason (collaboration, shared prizes, the same editors).

The old null shuffled gender within field × decade. The revised null shuffles within link community × decade, so topical
clustering of women cannot produce the result. Louvain communities change with the seed, so this is repeated over 10 partitions.
""")
code("""
print(f"{r3['women_to_women_edges']} of {r3['edges_to_women']} links to women's pages come from women's pages = {r3['observed_share_from_women']:.1%}")
display(pd.DataFrame([{"seed": s["seed"], **{k: round(s[k]["null_mean"], 3) for k in ("community", "community_x_decade")}, "z (community x decade)": round(s["community_x_decade"]["z"], 1)} for s in r3["by_louvain_seed"]]).set_index("seed").T)
display(Image(str(FIG / "fig3_homophily.png")))
""")
md("""
**Figure 3.** (A) Observed share against both nulls. (B) Share of women in each link community with at least 100 pages.

## 4. RQ2: how the pages are written

**Captures:** whether wording differs systematically once names, pronouns and gender words are masked.
**Misses:** what the difference is about. A classifier can pick up who wrote the page as easily as how the person is described.
""")
code("""
c = r2["classifier_strict_masking"]
print("metadata only (field, decade, citations, length):  AUC", round(r2["metadata_only_auc"], 3))
for k in ("pooled_auc", "within_field_decade_auc"):
    print(f"{k:<26} observed {c[k]['observed']:.3f} | shuffled {c[k]['null_mean']:.3f} {np.round(c[k]['null_ci95'], 3)} | z = {c[k]['z']:.1f}")
print("\\nstrongest classifier words, women's side:", ", ".join(c["top_features_women"][:25]))
print("strongest classifier words, men's side:  ", ", ".join(c["top_features_men"][:25]))
display(Image(str(FIG / "fig2_text.png")))
""")
md("""
**Figure 2.** (A) Cross-validated AUC within field × decade against 200 re-runs with shuffled gender. (B) Words by log-odds
z-score within field × birth decade; the tick marks show the value without the decade adjustment.

A caveat we found ourselves: British spellings and a recognisable biography style are among the women-side words.
""")
code("""
fw = pd.read_csv(RES / "rq2_words.csv").set_index("word")
display(fw.loc[["whilst", "honours", "characterisation", "considers", "postdoctoral", "earned", "theory", "papers"], ["share_women", "share_men", "z_pooled", "z_within_field_decade", "z_young_vs_old_men"]].round(3))
print("held-out replication:", r2["words"]["split_half"])
print("explicit gender mentions:", r2["explicit_gender_mentions"])
""")
md("""
## 5. Validation status

The blind sheets in `../validation/` are waiting for two human labellers. Until `r5_validation.py score` has been run,
the only labels are AI-assisted.
""")
code("""
import os
for f in sorted(os.listdir(VAL)):
    if f.endswith(".csv"):
        t = pd.read_csv(VAL / f); col = "correct" if "matches" in f else "is_personal"
        print(f"{f:<32} {t[col].notna().sum():>3} of {len(t)} rows labelled")
""")
md("""
## 6. Conclusions

See `../CONCLUSIONS.md` for the full tables. In short:

1. At equal citations, field and birth decade, women's pages receive about 40% fewer links from other scientists' pages. They also give fewer links and are more often isolated: less embedded in both directions.
2. The gap holds with subfield strata, with prose-only links (where it is larger), without Nobel laureates, among living people, and in physics, chemistry and biology alike. It is the same size among pages that could not be matched to OpenAlex.
3. Links to women's pages come from women's pages more than topic clusters and cohort account for.
4. The masked text still separates women's from men's pages. The words point to training and career steps on women's pages and to the work and its standing on men's, but page authorship is an untested alternative.
5. Open: human validation, the name-match selection check, and page creation dates.
""")
nb["cells"] = C
nbf.write(nb, "who_gets_remembered_revised.ipynb")
