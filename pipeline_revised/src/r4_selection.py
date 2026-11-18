"""R4. Selection check: is the gap an artefact of who could be matched to OpenAlex?

Only ~30% of physics/chemistry pages have an ORCID or OpenAlex ID on Wikidata, and the matched
women are much younger than the matched men. Three checks that need no new data:
  1. match rate by gender x birth decade (how selected the comparison set is)
  2. the in-degree gap among ALL pages, matched and unmatched separately. Citations are unknown for
     unmatched pages, so this controls field, decade, deceased, page length and prizes only. If the
     gap were created by the matching, it would be absent among unmatched pages.
  3. inverse-probability weighting: the comparison set reweighted to resemble all pages
     (probability of being matched modelled from gender, decade, field, page length, links, prizes).
A fourth check needs the OpenAlex API (not reachable from the machine this was run on):
  4. r4b_openalex_namematch.py name-matches a random sample of unmatched people; if
     data/impact_namematch.csv exists, the at-equal-citations model is re-run on that sample here.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from common import DATA, SEED, add_degrees, graph, load_nodes, perm_summary, permute_within, save_json
from r1_embeddedness import irr, negbin

NOIMPACT = "female + C(field_group) + C(birth_decade) + deceased + log_words + nobel + np.log10(1 + n_awards)"


def main():
    rng = np.random.default_rng(SEED)
    n = load_nodes()
    n = n[n.main_field]
    n = add_degrees(n, graph(n, "all"))
    k = n[n.gender_known].copy()
    k["n_awards"] = k.n_awards.fillna(0)
    k["log_links_page"] = np.log10(1 + k.n_links_all)
    out = {"pages_gender_known": len(k), "usable": int(k.usable.sum())}

    mr = k.groupby(["birth_decade", "gender"]).usable.agg(["mean", "size"]).unstack()
    out["match_rate_by_decade"] = {str(dec): {"women": float(r[("mean", "female")]), "men": float(r[("mean", "male")]),
                                              "n_women": int(r[("size", "female")]), "n_men": int(r[("size", "male")])}
                                   for dec, r in mr.iterrows()}
    out["share_born_1970_or_later"] = {
        "matched_women": float((k[k.usable & (k.female == 1)].birth_year >= 1970).mean()),
        "matched_men": float((k[k.usable & (k.female == 0)].birth_year >= 1970).mean()),
        "all_women": float((k[k.female == 1].birth_year >= 1970).mean()),
        "all_men": float((k[k.female == 0].birth_year >= 1970).mean())}

    groups = {"all pages": k, "matched (comparison set)": k[k.usable], "not matched": k[~k.usable]}
    out["gap_without_citation_control"] = {}
    for name, s in groups.items():
        codes = pd.factorize(s.field_group + "|" + s.birth_decade.astype(str))[0]
        f, y = s.female.to_numpy(), s.in_degree.to_numpy(float)
        null = np.array([y[permute_within(f, codes, rng) == 1].mean() for _ in range(500)])
        p = perm_summary(y[f == 1].mean(), null)
        out["gap_without_citation_control"][name] = {
            "n": len(s), "women": int(f.sum()),
            "raw_mean_in_degree": s.groupby("gender").in_degree.mean().round(3).to_dict(),
            "raw_isolate_share": s.groupby("gender").isolate.mean().round(3).to_dict(),
            "perm_ratio_field_decade": p["observed"] / p["null_mean"], "perm_z": p["z"],
            "negbin_irr": irr(negbin(s, "in_degree", NOIMPACT))}

    # 3. inverse-probability weights
    ps = smf.logit("usable_i ~ female * C(birth_decade) + C(field_group) + deceased + log_words + log_links_page"
                   " + nobel + np.log10(1 + n_awards)", k.assign(usable_i=k.usable.astype(int))).fit(disp=0)
    d = k[k.usable].copy()
    d["w"] = 1 / ps.predict(d)
    d["w"] = d.w.clip(upper=d.w.quantile(0.99))
    d["log_cit"] = np.log10(d.citations)
    rhs = "female + log_cit + C(field_group) + C(birth_decade) + deceased"
    m0 = smf.glm(f"in_degree ~ {rhs}", d, family=sm.families.Poisson()).fit(cov_type="HC1")
    m1 = smf.glm(f"in_degree ~ {rhs}", d, family=sm.families.Poisson(), var_weights=d.w).fit(cov_type="HC1")
    out["ipw"] = {"unweighted_poisson": irr(m0), "weighted_poisson": irr(m1),
                  "effective_sample_size": float(d.w.sum() ** 2 / (d.w ** 2).sum()),
                  "max_weight": float(d.w.max())}

    f = DATA / "impact_namematch.csv"
    if f.exists():
        nm = pd.read_csv(f).set_index("qid")
        s = k.join(nm[["nm_citations"]], how="inner")
        s = s[s.nm_citations > 0].assign(log_cit=lambda x: np.log10(x.nm_citations))
        out["name_matched_sample"] = {"n": len(s), "women": int(s.female.sum()),
                                      "negbin_irr": irr(negbin(s, "in_degree", rhs))}
    else:
        out["name_matched_sample"] = "not run: needs the OpenAlex API (see r4b_openalex_namematch.py)"
    save_json(out, "selection_check.json")
    return out


if __name__ == "__main__":
    o = main()
    print(pd.DataFrame(o["match_rate_by_decade"]).T.round(2))
    print(o["share_born_1970_or_later"])
    for k_, v in o["gap_without_citation_control"].items():
        print(k_, v)
    print(o["ipw"])
