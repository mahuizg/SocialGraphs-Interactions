"""R1. RQ1 revised: are women's pages less *embedded* in the scientist link network at equal impact?

Headline outcome: raw in-degree (number of other scientists' pages linking to the page), with
out-degree, reciprocal links, zero-in-link pages and isolates beside it. PageRank is a supplement row.

Checks, in the order they appear in results/rq1_embeddedness.json
  descriptives   raw means by gender (not adjusted; never quoted as 'at equal impact')
  permutation    gender shuffled within strata, network fixed, 1,000 runs. Statistic: women's mean
                 outcome; ratio = observed / mean under shuffling. Two strata definitions:
                 field x decade x citation quintile, and subfield x decade x citation tercile.
                 Because node labels are permuted on a fixed network, the test stays valid even
                 though in-degrees of neighbouring pages are not independent.
  count models   Poisson (robust SE) and negative binomial incidence-rate ratios for `female`,
                 a hurdle model (any in-link? / how many, given any), a ladder of extra controls
                 (subfield, page length, links on the page, out-degree), and Poisson with SEs
                 clustered by link community.
  robustness     prose-only edges, h-index, single-profile matches only, no Nobel, no top 1%.
  field x gender one model over physics, chemistry and biology on the full three-field network.
"""
import warnings

import networkx as nx
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.discrete.truncated_model import TruncatedLFNegativeBinomialP

from common import SEED, add_degrees, comparison_set, graph, load_nodes, perm_summary, permute_within, save_json

warnings.filterwarnings("ignore")
RUNS = 1000
BASE = "female + log_cit + C(field_group) + C(birth_decade) + deceased"
OUTCOMES = ["in_degree", "out_degree", "reciprocal", "zero_in", "zero_out", "isolate"]


def prep(d):
    d = d.copy()
    d["zero_in"] = (d.in_degree == 0).astype(int)
    d["zero_out"] = (d.out_degree == 0).astype(int)
    d["log_links_page"] = np.log10(1 + d.n_links_all)
    d["log_out"] = np.log10(1 + d.out_degree)
    d["log_pr"] = np.log10(d.pagerank)
    return d


def descriptives(d):
    g = d.groupby("gender")
    out = {"n": g.size().to_dict()}
    for c in OUTCOMES:
        out[c] = g[c].mean().round(4).to_dict()
    out["median_birth_year"] = g.birth_year.median().to_dict()
    return out


def permutation(d, strata_col, rng, runs=RUNS, cols=OUTCOMES):
    codes = pd.factorize(d[strata_col])[0]
    f = d.female.to_numpy()
    Y = d[cols].to_numpy(float)
    obs = Y[f == 1].mean(0)
    null = np.empty((runs, len(cols)))
    for i in range(runs):
        null[i] = Y[permute_within(f, codes, rng) == 1].mean(0)
    k = pd.crosstab(codes, f)
    res = {"strata": int(len(k)), "strata_with_both_genders": int(((k[0] > 0) & (k[1] > 0)).sum()),
           "women_in_mixed_strata": int(k[1][(k[0] > 0) & (k[1] > 0)].sum())}
    for j, c in enumerate(cols):
        s = perm_summary(obs[j], null[:, j])
        s["ratio_obs_over_null"] = s["observed"] / s["null_mean"]
        s["ratio_null_ci95"] = [x / s["null_mean"] for x in s["null_ci95"]]
        res[c] = s
    return res, null


def irr(m, name="female"):
    b, (lo, hi) = m.params[name], m.conf_int().loc[name]
    return {"irr": float(np.exp(b)), "ci95": [float(np.exp(lo)), float(np.exp(hi))], "p": float(m.pvalues[name]),
            "n": int(m.nobs)}


def poisson(d, y, rhs, cluster=None):
    kw = {"cov_type": "cluster", "cov_kwds": {"groups": d[cluster]}} if cluster else {"cov_type": "HC1"}
    return smf.glm(f"{y} ~ {rhs}", d, family=sm.families.Poisson()).fit(**kw)


def negbin(d, y, rhs):
    start = np.r_[poisson(d, y, rhs).params.to_numpy(), 1.0]
    return smf.negativebinomial(f"{y} ~ {rhs}", d).fit(start_params=start, method="bfgs", maxiter=2000,
                                                       disp=0, cov_type="HC1")


def hurdle(d, y, rhs):
    """Part 1: does the page get any link (logit)? Part 2: how many, given at least one (zero-truncated NB)."""
    d = d.assign(any_=(d[y] > 0).astype(int))
    m1 = smf.logit(f"any_ ~ {rhs}", d).fit(disp=0, cov_type="HC1")
    ame = m1.get_margeff().summary_frame().loc["female"]
    pos = d[d[y] > 0]
    X = smf.ols(f"{y} ~ {rhs}", pos).data.exog          # design matrix only
    names = smf.ols(f"{y} ~ {rhs}", pos).data.xnames
    p0 = np.r_[sm.GLM(pos[y] - 1, X, family=sm.families.Poisson()).fit().params, 0.5]
    m2 = TruncatedLFNegativeBinomialP(pos[y].to_numpy(), X, truncation=0).fit(
        start_params=p0, method="bfgs", maxiter=2000, disp=0, cov_type="HC1")
    j = names.index("female")
    b, se = m2.params[j], m2.bse[j]
    return {"any_link_share": d.groupby("gender").any_.mean().to_dict(),
            "any_link_odds_ratio": irr(m1)["irr"], "any_link_odds_ratio_ci95": irr(m1)["ci95"],
            "any_link_diff_pct_points": float(100 * ame["dy/dx"]),
            "any_link_diff_ci95": [float(100 * ame["Conf. Int. Low"]), float(100 * ame["Cont. Int. Hi."])],
            "count_given_any_rate_ratio": float(np.exp(b)),
            "count_given_any_ci95": [float(np.exp(b - 1.96 * se)), float(np.exp(b + 1.96 * se))],
            "count_given_any_p": float(2 * (1 - __import__("scipy.stats").stats.norm.cdf(abs(b / se)))),
            "n_with_any": int(len(pos)), "women_with_any": int(pos.female.sum()),
            "note": "count part = ratio of the latent NB mean; zero-truncated negative binomial"}


def models(d, y="in_degree"):
    out = {"poisson_robust": irr(poisson(d, y, BASE))}
    nb = negbin(d, y, BASE)
    out["negative_binomial"] = {**irr(nb), "alpha": float(nb.params["alpha"])}
    out["hurdle"] = hurdle(d, y, BASE)
    return out


def ladder(d, y="in_degree"):
    """How the gap moves as controls are added. The last rows are mediators, not confounders:
    they show what the gap runs through, they do not 'explain it away'."""
    specs = [("baseline: citations, field, decade, deceased", BASE),
             ("+ subfield (OpenAlex)", BASE + " + C(subfield)"),
             ("+ page length (log words)", BASE + " + C(subfield) + log_words"),
             ("+ links on the page (log)", BASE + " + C(subfield) + log_words + log_links_page"),
             ("+ out-degree to scientists (log)", BASE + " + C(subfield) + log_words + log_links_page + log_out"),
             ("+ Nobel and awards", BASE + " + C(subfield) + nobel + np.log10(1 + n_awards.fillna(0))")]
    return [{"spec": n, **irr(negbin(d, y, r))} for n, r in specs]


def clustered(d, U):
    """Poisson IRR with SEs clustered by Louvain community (isolated pages = own cluster)."""
    comm = {n: i for i, c in enumerate(nx.community.louvain_communities(U, seed=0)) for n in c}
    d = d.assign(cl=[comm[q] for q in d.index])
    return {**irr(poisson(d, "in_degree", BASE, cluster="cl")), "clusters": int(d.cl.nunique())}


def pagerank_supplement(d):
    m = smf.ols(f"log_pr ~ {BASE}", d).fit(cov_type="HC3")
    b, (lo, hi) = m.params["female"], m.conf_int().loc["female"]
    return {"ratio_geometric": float(10 ** b), "ci95": [float(10 ** lo), float(10 ** hi)],
            "note": "log10 PageRank; with ~half the pages at the PageRank floor this is close to a "
                    "transformed in-degree, so it understates the gap in links (supplement only)"}


def run_one(nodes, edges, rng, fields_main=True, runs=RUNS):
    n = nodes[nodes.main_field] if fields_main else nodes
    G = graph(n, edges)
    n = add_degrees(n, G)
    d = prep(comparison_set(n))
    return n, G, d


def main():
    rng = np.random.default_rng(SEED)
    nodes = load_nodes()
    n, G, d = run_one(nodes, "all", rng)
    out = {"graph": {"edge_definition": "all wikilinks", "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                     "isolates": nx.number_of_isolates(G)},
           "comparison_set": {"n": len(d), "women": int(d.female.sum()), "men": int((1 - d.female).sum())},
           "descriptives_raw": descriptives(d)}
    nulls = {}
    for key, col in (("field_decade_citation5", "stratum"), ("subfield_decade_citation3", "stratum_sub")):
        out[f"permutation_{key}"], nulls[key] = permutation(d, col, rng)
    out["models_in_degree"] = models(d, "in_degree")
    out["models_out_degree"] = models(d, "out_degree")
    out["ladder_in_degree_negbin"] = ladder(d)
    out["clustered_by_community"] = clustered(d, G.to_undirected())
    out["pagerank_supplement"] = pagerank_supplement(d)
    np.save(__import__("common").RES / "rq1_null_draws.npy", nulls["field_decade_citation5"])

    # ---- robustness
    rob = []

    def row(name, dd, rhs=BASE):
        p, _ = permutation(dd, "stratum", np.random.default_rng(SEED), runs=500, cols=["in_degree", "out_degree", "isolate"])
        nb = irr(negbin(dd, "in_degree", rhs))
        rob.append({"variant": name, "n": len(dd), "women": int(dd.female.sum()),
                    "in_degree_ratio_perm": p["in_degree"]["ratio_obs_over_null"], "z": p["in_degree"]["z"],
                    "in_degree_irr_nb": nb["irr"], "irr_lo": nb["ci95"][0], "irr_hi": nb["ci95"][1],
                    "out_degree_ratio_perm": p["out_degree"]["ratio_obs_over_null"],
                    "isolate_ratio_perm": p["isolate"]["ratio_obs_over_null"]})

    row("Main: all wikilinks", d)
    if __import__("common").EDGE_FILES["prose"].exists():
        _, Gp, dp = run_one(nodes, "prose", rng)
        out["graph_prose"] = {"edges": Gp.number_of_edges(), "isolates": nx.number_of_isolates(Gp)}
        out["descriptives_raw_prose"] = descriptives(dp)
        out["models_in_degree_prose"] = models(dp, "in_degree")
        row("Prose-only links", dp)
    row("Subfield strata + subfield control", d.assign(stratum=d.stratum_sub), BASE + " + C(subfield)")
    dh = d[d.h_index > 0].assign(log_cit=lambda x: np.log10(x.h_index))
    dh["stratum"] = dh.field_group + "|" + dh.birth_decade.astype(str) + "|" + pd.qcut(
        dh.log_cit.rank(method="first"), 5, labels=False).astype(str)
    row("Impact = h-index (largest profile)", dh)
    row("Single OpenAlex profile only", prep(comparison_set(n[n.n_profiles == 1])))
    row("Without Nobel laureates", prep(comparison_set(n[n.nobel == 0])))
    row("Without top 1% by citations", prep(comparison_set(n[~(n.citations >= d.citations.quantile(0.99))])))
    row("Born 1950 or later", prep(comparison_set(n[n.birth_year >= 1950])))
    row("Living people only", prep(comparison_set(n[n.deceased == 0])), BASE.replace(" + deceased", ""))
    out["robustness"] = rob
    pd.DataFrame(rob).round(3).to_csv(__import__("common").RES / "rq1_robustness.csv", index=False)

    # ---- field x gender in one model, full three-field network
    nf, Gf, df = run_one(nodes, "all", rng, fields_main=False)
    df = prep(comparison_set(nf, fields=("physics", "chemistry", "biology")))
    rhs = "female * C(field_group, Treatment('physics')) + log_cit + C(birth_decade) + deceased"
    m = negbin(df, "in_degree", rhs)
    fx = {"n": int(m.nobs), "graph_nodes": Gf.number_of_nodes(), "graph_edges": Gf.number_of_edges(),
          "by_field": {}}
    for fld in ("physics", "chemistry", "biology"):
        if fld == "physics":
            b, se = m.params["female"], m.bse["female"]
        else:
            t = f"female:C(field_group, Treatment('physics'))[T.{fld}]"
            L = np.zeros(len(m.params))
            L[list(m.params.index).index("female")] = 1
            L[list(m.params.index).index(t)] = 1
            tt = m.t_test(L)
            b, se = float(tt.effect[0]), float(tt.sd[0][0])
            fx["by_field"].setdefault(fld, {})["interaction_p_vs_physics"] = float(m.pvalues[t])
        s = df[df.field_group == fld]
        fx["by_field"].setdefault(fld, {}).update(
            {"irr": float(np.exp(b)), "ci95": [float(np.exp(b - 1.96 * se)), float(np.exp(b + 1.96 * se))],
             "n": len(s), "women": int(s.female.sum()),
             "raw_mean_in_degree": s.groupby("gender").in_degree.mean().round(3).to_dict(),
             "raw_isolate_share": s.groupby("gender").isolate.mean().round(3).to_dict()})
    terms = [t for t in m.params.index if t.startswith("female:")]
    fx["joint_interaction_p"] = float(m.wald_test(terms, scalar=True).pvalue)
    mw = smf.ols("log_words ~ " + rhs, df).fit(cov_type="HC3")
    fx["page_length_ratio_physics"] = float(10 ** mw.params["female"])
    fx["page_length_ratio_biology"] = float(10 ** (mw.params["female"] + mw.params[
        "female:C(field_group, Treatment('physics'))[T.biology]"]))
    out["field_by_gender"] = fx

    save_json(out, f"rq1_embeddedness_runs{RUNS}.json")
    d[["title", "gender", "female", "field_group", "subfield", "birth_decade", "citations", "log_cit", "cit_bin",
       "in_degree", "out_degree", "reciprocal", "isolate", "zero_in", "pagerank", "n_words"]].to_csv(
        __import__("common").RES / "rq1_comparison_set.csv")
    return out


if __name__ == "__main__":
    o = main()
    print(o["descriptives_raw"])
    for k in ("permutation_field_decade_citation5", "permutation_subfield_decade_citation3"):
        print(k, {c: (round(o[k][c]["ratio_obs_over_null"], 3), round(o[k][c]["z"], 1)) for c in OUTCOMES})
    print(o["models_in_degree"]); print(o["models_out_degree"])
    for r in o["ladder_in_degree_negbin"]:
        print(f"{r['spec']:<50} {r['irr']:.3f} [{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}]")
    print(o["clustered_by_community"], o["pagerank_supplement"])
    print(pd.DataFrame(o["robustness"]).round(3).to_string())
    print(o["field_by_gender"])
