"""Extra analysis (history): how women's and men's scientist pages were created and edited over the years.

ADD-ON to the paper. It does not change or re-run anything that already exists: it reads
nodes.csv / edges (read-only) and the edit histories collected by r6a_history_collect.py, and writes only
  results/rq4_history_*.json|csv      figures/history/*.pdf|png      HISTORY_CONCLUSIONS.md

Questions (all on the paper's network: physics, chemistry, phys+chem; biology repeated as a check)
  H1  When were the pages created? Women's share of new pages per year; creation year at equal field x decade.
  H2  How much are pages edited over the years? Human edits and editors per page-year, page length over time.
  H3  Who created them? Concentration of page creators, Articles for creation, WikiProject banners.
  H4  What kind of edits? Edit summaries and edited sections classified (reverts, deletion / notability /
      orphan tags, references, links, categories, personal life, awards ...), women vs men at equal page age.
  H5  Editor-page network: are women's pages edited by the same people (bipartite homophily vs shuffle)?

Comparisons follow the paper's logic: gender is shuffled within field x birth decade (1,000 runs), and count
models compare women and men at the same page age (exposure = years since creation) and creation period.
Bots are removed (bot user group + 'Bot' account names). Usernames are never written to the outputs.

    python r6b_history_analysis.py            # ~2-5 min
"""
import gzip
import json
import re
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.sparse as sp
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from common import COL, DATA, FIG, RES, ROOT, SEED, load_nodes, perm_summary, permute_within

warnings.filterwarnings("ignore")
HIST = DATA / "history"
OUT = FIG / "history"
OUT.mkdir(parents=True, exist_ok=True)
CUTOFF = pd.Timestamp("2026-11-13T23:59:59Z")
RUNS = 1000
CONTROLS = "C(field_group) + C(birth_decade) + C(created_bin)"
CREATED_BINS = [2000, 2006, 2010, 2015, 2020, 2027]
CREATED_LABELS = ["2001-05", "2006-09", "2010-14", "2015-19", "2020-26"]

# ------------------------------------------------------------------ edit classification
# keyword types are matched on the edit summary with the "/* section */" part removed;
# the section part is classified separately (which section of the page was edited).
REVERT_TAGS = re.compile(r"mw-undo|mw-rollback|mw-manual-revert")
TYPES = {
    "revert": r"\b(revert(ed|ing)?|undid|undo|rvv?|rollback)\b",
    "deletion_nomination": r"(articles for deletion|\bafd\b|proposed deletion|\bprod\b|blpprod|speedy deletion|"
                           r"\bcsd\b|nominat\w* for deletion)",
    "notability_tag": r"notab",
    "orphan_tag_added": r"orphan",                    # removal summaries are split off below
    "orphan_tag_removed": r"orphan",
    "maintenance_tag": r"(\btag(s|ged|ging)?\b|citation needed|refimprove|more citations|unreferenced|one source|"
                       r"primary sources|\bblp\w*\b|cleanup|peacock|puffery|\bcoi\b|autobiograph|advert)",
    "references": r"(\bref(s|erence|erences)?\b|citation|\bcite[sd]?\b|\bsources?\b|sourced)",
    "wikilinks": r"(\blinks?\b|wikilink|wikify|\blinked\b|\[\[)",
    "categories": r"(categor|hotcat)",
    "infobox_wikidata": r"(infobox|wikidata|authority control|short description)",
    "copyedit": r"(typo|copy ?edit|\bce\b|grammar|spelling|punctuation|\bmos\b|wording)",
    "personal_life": r"(personal life|married|marriage|husband|wife|spouse|children|daughter|\bson\b|family|"
                     r"divorc|mother|father)",
    "awards": r"(award|prize|medal|fellow|honou?r|laureate)",
    "career_research": r"(research|career|professor|appointed|university|publication|discover|thesis|phd)",
}
TYPES = {k: re.compile(v) for k, v in TYPES.items()}
ORPHAN_REMOVED = re.compile(r"(remov|de-?orphan|no longer|not an? orphan|untag|delete)")
SECTIONS = {
    "sec_personal": r"(personal|family|private life|marriage)",
    "sec_early_education": r"(early life|education|childhood|early years)",
    "sec_career_research": r"(career|research|work|scientific|contribution|academic|scien)",
    "sec_awards": r"(award|honou?r|prize|recognition|distinction)",
    "sec_references_links": r"(reference|external link|further reading|notes|bibliography|publication|selected)",
    "sec_death_legacy": r"(death|legacy|later life)",
}
SECTIONS = {k: re.compile(v) for k, v in SECTIONS.items()}
SEC_RE = re.compile(r"/\*\s*(.*?)\s*\*/")
BOT_NAME = re.compile(r"(Bot\b|Bot$|[_\- ]bot$|^bot[_\- ])")
LABELS = {
    "revert": "Reverts", "reverted_later": "Edits later reverted", "deletion_nomination": "Deletion nominations",
    "notability_tag": "Notability tags", "orphan_tag_added": "Orphan tag added",
    "orphan_tag_removed": "Orphan tag removed", "maintenance_tag": "Maintenance tags",
    "references": "References", "wikilinks": "Wikilinks", "categories": "Categories",
    "infobox_wikidata": "Infobox / Wikidata", "copyedit": "Copy-edits", "personal_life": "Personal life (summary)",
    "awards": "Awards (summary)", "career_research": "Career / research (summary)",
    "sec_personal": "Personal-life section", "sec_early_education": "Early life / education section",
    "sec_career_research": "Career / research section", "sec_awards": "Awards section",
    "sec_references_links": "References / links section", "sec_death_legacy": "Death / legacy section",
    "n_edits": "All human edits", "n_editors": "Distinct human editors", "large_additions": "Large additions (>1 kB)",
}


# ------------------------------------------------------------------ loading
def load_revisions():
    rows = []
    for f in sorted((HIST / "revisions").glob("part_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                for r in d["revs"]:
                    rows.append([d["qid"], *r])
    cols = ["qid", "ts", "user", "userid", "anon", "size", "minor", "comment", "tags", "revid", "parentid"]
    rv = pd.DataFrame(rows, columns=cols).drop_duplicates(["qid", "revid"])
    rv["ts"] = pd.to_datetime(rv.ts, utc=True, format="ISO8601")
    rv = rv[rv.ts <= CUTOFF].sort_values(["qid", "ts", "revid"]).reset_index(drop=True)
    rv["comment"] = rv.comment.fillna("")
    rv["tags"] = rv.tags.fillna("")
    bots = set(json.loads((HIST / "bots.json").read_text(encoding="utf-8"))) if (HIST / "bots.json").exists() else set()
    u = rv.user.fillna("")
    rv["bot"] = u.isin(bots) | u.str.contains(BOT_NAME) | rv.tags.str.contains("bot", case=False)
    return rv


def page_table(rv, nodes):
    """One row per page: creation, creator, age, activity and edit-type counts (human edits only)."""
    g = rv.groupby("qid", sort=False)
    first = g.head(1).set_index("qid")
    # a page that started as a redirect counts from its first revision of >= 1,000 bytes
    # (very short new articles are NOT redirects and keep their first revision as creation)
    big = rv[rv["size"] >= 1000].groupby("qid").head(1).set_index("qid")
    start = first.copy()
    is_redirect = first.tags.str.contains("mw-new-redirect") | first.comment.str.contains(r"redirect", case=False)
    swap = first.index[is_redirect & (first["size"] < 200) & first.index.isin(big.index)]
    start.loc[swap] = big.loc[swap]
    p = pd.DataFrame({"created": start.ts, "creator": start.user.fillna("(hidden)"),
                      "creator_anon": start.anon, "creator_bot": start.bot,
                      "started_as_redirect": first.index.isin(swap)})
    p["created_year"] = p.created.dt.year
    p["created_bin"] = pd.cut(p.created_year, CREATED_BINS, right=False, labels=CREATED_LABELS).astype(str)
    p["page_years"] = ((CUTOFF - p.created).dt.days / 365.25).clip(lower=0.1)
    p["final_size"] = g["size"].last()

    rv = rv.merge(p[["created"]], left_on="qid", right_index=True)
    h = rv[(~rv.bot) & (rv.ts > rv.created)].copy()          # human edits after the article started
    # size change relative to the previous revision of the page (including bot revisions)
    prev = rv.groupby("qid")["size"].shift()
    h["delta"] = (rv.loc[h.index, "size"] - prev.loc[h.index]).fillna(0)

    sec = h.comment.str.extract(SEC_RE, expand=False).fillna("").str.lower()
    body = h.comment.str.replace(SEC_RE, " ", regex=True).str.lower()
    for k, rx in TYPES.items():
        h[k] = body.str.contains(rx)
    rem = body.str.contains(ORPHAN_REMOVED)
    h["orphan_tag_removed"] &= rem
    h["orphan_tag_added"] &= ~rem
    h["revert"] |= h.tags.str.contains(REVERT_TAGS)
    h["reverted_later"] = h.tags.str.contains("mw-reverted")
    h["large_additions"] = h.delta > 1000
    for k, rx in SECTIONS.items():
        h[k] = sec.str.contains(rx) & (sec != "")
    kinds = list(TYPES) + ["reverted_later", "large_additions"] + list(SECTIONS)

    hg = h.groupby("qid")
    p["n_edits"] = hg.size()
    p["n_editors"] = hg.user.nunique()
    p["n_registered_editors"] = h[h.anon == 0].groupby("qid").user.nunique()
    p["share_anon_edits"] = hg.anon.mean()
    for k in kinds:
        p[k] = hg[k].sum()
    p = p.fillna({c: 0 for c in ["n_edits", "n_editors", "n_registered_editors"] + kinds})
    for c in ["n_edits", "n_editors", "n_registered_editors"] + kinds:
        p[c] = p[c].astype(int)

    talk = HIST / "talk_templates.csv"
    if talk.exists():
        t = pd.read_csv(talk).set_index("qid").templates.fillna("")
        t = t.reindex(p.index).fillna("")
        flags = {"talk_women_in_red": r"WikiProject Women in Red", "talk_women_scientists": r"WikiProject Women scientists",
                 "talk_any_women_project": r"WikiProject Wom[ae]n", "talk_afc": r"WikiProject Articles for creation",
                 "talk_old_afd": r"Old ?AfD|Oldafdfull|Old ?XfD|Afd", "talk_old_prod": r"Old ?prod",
                 "talk_connected_contributor": r"Connected contributor|COI", "talk_dyk": r"DYK|Did you know"}
        for k, rx in flags.items():
            p[k] = t.str.contains(rx, case=False).astype(int)

    p = p.join(nodes[["title", "gender", "female", "field_group", "birth_decade", "citations", "usable"]], how="inner")
    return p, h, kinds


# ------------------------------------------------------------------ helpers
def strata_codes(p):
    return pd.factorize(p.field_group.astype(str) + "|" + p.birth_decade.astype(str))[0]


def perm_diff(p, col, rng, runs=RUNS):
    """Women minus men mean of `col`, against gender shuffled within field x decade."""
    v = p[col].to_numpy(float)
    f = p.female.to_numpy()
    codes = strata_codes(p)
    stat = lambda ff: v[ff == 1].mean() - v[ff == 0].mean()
    null = [stat(permute_within(f, codes, rng)) for _ in range(runs)]
    return {"women_mean": float(v[f == 1].mean()), "men_mean": float(v[f == 0].mean()),
            **perm_summary(stat(f), null)}


def nb_irr(d, y, extra="", exposure="page_years"):
    """Rate ratio women/men for count y at equal page age (exposure) and controls. NB, Poisson as fallback."""
    form = f"{y} ~ female + {CONTROLS}{extra}"
    out = {"outcome": y, "n": int(len(d)), "women_total": int(d.loc[d.female == 1, y].sum()),
           "men_total": int(d.loc[d.female == 0, y].sum())}
    if min(out["women_total"], out["men_total"]) < 5:
        out.update(model="too few events", rate_ratio=np.nan, ci95=[np.nan, np.nan], p=np.nan)
        return out
    try:
        m = smf.negativebinomial(form, d, exposure=d[exposure]).fit(disp=0, maxiter=300, cov_type="HC0")
        if not m.mle_retvals.get("converged", True) or not np.isfinite(m.bse["female"]):
            raise RuntimeError
        out["model"] = "negative binomial (robust SE)"
    except Exception:
        try:
            m = smf.glm(form, d, family=sm.families.Poisson(), offset=np.log(d[exposure])).fit(cov_type="HC0")
            out["model"] = "poisson (robust SE)"
        except Exception as e:
            out.update(model=f"failed: {repr(e)[:80]}", rate_ratio=np.nan, ci95=[np.nan, np.nan], p=np.nan)
            return out
    b, (lo, hi) = m.params["female"], m.conf_int().loc["female"]
    out.update(rate_ratio=float(np.exp(b)), ci95=[float(np.exp(lo)), float(np.exp(hi))], p=float(m.pvalues["female"]))
    return out


def logit_or(d, y):
    form = f"{y} ~ female + {CONTROLS} + np.log(page_years)"
    out = {"outcome": y, "n": int(len(d)), "women_share": float(d.loc[d.female == 1, y].mean()),
           "men_share": float(d.loc[d.female == 0, y].mean())}
    try:
        m = smf.logit(form, d).fit(disp=0, maxiter=300)
        b, (lo, hi) = m.params["female"], m.conf_int().loc["female"]
        out.update(odds_ratio=float(np.exp(b)), ci95=[float(np.exp(lo)), float(np.exp(hi))], p=float(m.pvalues["female"]))
    except Exception as e:
        out["error"] = repr(e)[:120]
    return out


def gini(x):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())) if n and x.sum() else float("nan")


def top_share(creators, k=10):
    vc = pd.Series(creators).value_counts()
    return float(vc.head(k).sum() / vc.sum())


# ------------------------------------------------------------------ H1-H5
def h1_creation(p, rng):
    yr = p.groupby(["created_year", "gender"]).size().unstack(fill_value=0)
    yr["women_share"] = yr.get("female", 0) / yr.sum(axis=1)
    out = {"by_year": yr.reset_index().to_dict("records"),
           "median_created_year": p.groupby("gender").created_year.median().to_dict(),
           "share_created_2015_or_later": p.assign(x=p.created_year >= 2015).groupby("gender").x.mean().to_dict(),
           "created_year_women_minus_men": perm_diff(p, "created_year", rng),
           "started_as_redirect": p.groupby("gender").started_as_redirect.mean().to_dict()}
    yr.to_csv(RES / "rq4_history_created_by_year.csv")
    return out


def h2_activity(p, h, rv):
    rows = []
    for y in range(2003, 2026):
        alive = p[p.created < pd.Timestamp(f"{y}-01-01", tz="UTC")]
        if len(alive) < 20:
            continue
        e = h[(h.ts.dt.year == y) & h.qid.isin(alive.index)].groupby("qid").size().reindex(alive.index).fillna(0)
        ed = h[(h.ts.dt.year == y) & h.qid.isin(alive.index)].groupby("qid").user.nunique().reindex(alive.index).fillna(0)
        for g in ("female", "male"):
            m = alive.gender == g
            v = e[m]
            rows.append({"year": y, "gender": g, "pages": int(m.sum()), "edits_per_page": float(v.mean()),
                         "se": float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else np.nan,
                         "editors_per_page": float(ed[m].mean())})
    yearly = pd.DataFrame(rows)
    yearly.to_csv(RES / "rq4_history_edits_by_year.csv", index=False)

    # page length k years after the article started (size of the last revision before that moment)
    rv_sz = rv[rv.qid.isin(p.index)][["qid", "ts", "size"]].sort_values("ts")
    traj = []
    for k in range(0, 16):
        q = p[["created", "gender"]].copy()
        q["at"] = q.created + pd.Timedelta(days=round(365.25 * (k + 1)))
        q = q[q["at"] <= CUTOFF].reset_index().sort_values("at")
        if q.empty:
            continue
        m = pd.merge_asof(q, rv_sz, left_on="at", right_on="ts", by="qid", direction="backward")
        for g in ("female", "male"):
            v = m[m.gender == g]["size"].dropna()
            if len(v) >= 10:
                traj.append({"years_since_creation": k + 1, "gender": g, "n": int(len(v)),
                             "median_bytes": float(v.median())})
    traj = pd.DataFrame(traj)
    traj.to_csv(RES / "rq4_history_size_by_age.csv", index=False)

    models = {y: nb_irr(p, y) for y in ("n_edits", "n_editors", "large_additions")}
    matched = p[p.usable & (p.citations > 0)].assign(log_cit=lambda d: np.log10(d.citations))
    models_matched = {y: nb_irr(matched, y, extra=" + log_cit") for y in ("n_edits", "n_editors")}
    rates = p.assign(e=p.n_edits / p.page_years, ed=p.n_editors / p.page_years).groupby("gender")[["e", "ed"]].median()
    return yearly, traj, {"median_edits_per_year": rates.e.to_dict(), "median_editors_per_year": rates.ed.to_dict(),
                          "rate_ratios_equal_age": models, "rate_ratios_equal_age_and_citations": models_matched,
                          "median_final_size_bytes": p.groupby("gender").final_size.median().to_dict()}


def h3_creators(p, rng):
    reg = p[(p.creator_anon == 0) & (~p.creator_bot)]
    f = reg.female.to_numpy()
    codes = strata_codes(reg)
    cr = reg.creator.to_numpy()

    def stat(ff):
        return top_share(cr[ff == 1]) - top_share(cr[ff == 0])

    null = [stat(permute_within(f, codes, rng)) for _ in range(RUNS)]
    women_null = [top_share(cr[permute_within(f, codes, rng) == 1]) for _ in range(200)]
    vc = {g: reg[reg.gender == g].creator.value_counts() for g in ("female", "male")}
    lorenz = {}
    for g, v in vc.items():
        c = np.r_[0, np.cumsum(v.to_numpy()) / v.sum()]
        x = np.linspace(0, 1, len(c))
        lorenz[g] = (x, c)
    prolific = reg.creator.map(reg.creator.value_counts()) >= 10
    out = {"registered_human_creators": {g: int(v.size) for g, v in vc.items()},
           "pages_with_registered_human_creator": {g: int(v.sum()) for g, v in vc.items()},
           "pages_created_anonymously": p.groupby("gender").creator_anon.mean().to_dict(),
           "top10_creators_share": {g: top_share(reg[reg.gender == g].creator) for g in vc},
           "top10_share_women_minus_men": perm_summary(stat(f), null),
           "top10_share_women_if_gender_shuffled": {"mean": float(np.mean(women_null)),
                                                    "ci95": [float(x) for x in np.percentile(women_null, [2.5, 97.5])]},
           "gini_pages_per_creator": {g: gini(v.to_numpy()) for g, v in vc.items()},
           "share_by_creators_of_10plus_pages": reg.assign(x=prolific).groupby("gender").x.mean().to_dict(),
           "top10_creators_share_by_period": {
               per: {g: top_share(s[s.gender == g].creator) for g in vc if (s.gender == g).sum() >= 30}
               for per, s in (("before 2015", reg[reg.created_year < 2015]), ("2015 or later", reg[reg.created_year >= 2015]))}}
    # anonymised list of the most active creators: share of their created pages that are women's
    top = reg.creator.value_counts().head(20)
    out["top20_creators_anonymised"] = [{"creator": f"Editor {i + 1:02d}", "pages_created": int(n),
                                         "share_women": float(reg[reg.creator == c].female.mean())}
                                        for i, (c, n) in enumerate(top.items())]
    talk = [c for c in p.columns if c.startswith("talk_")]
    out["talk_page_templates"] = {c: perm_diff(p, c, rng, runs=300) for c in talk}
    return lorenz, out


def h4_edit_types(p, kinds):
    rows = [nb_irr(p, k) for k in kinds]
    t = pd.DataFrame(rows)
    t["label"] = t.outcome.map(LABELS)
    ok = t.p.notna()
    t.loc[ok, "p_holm"] = multipletests(t.loc[ok, "p"], method="holm")[1]
    cols = list(dict.fromkeys(["n_edits"] + kinds))
    tot = p.groupby("gender")[cols].sum()
    for g in ("female", "male"):
        t[f"share_of_{g}_edits"] = t.outcome.map(tot.loc[g, cols] / tot.loc[g, "n_edits"])
    t.to_csv(RES / "rq4_history_edit_types.csv", index=False)
    ever = {k: logit_or(p.assign(**{f"ever_{k}": (p[k] > 0).astype(int)}), f"ever_{k}")
            for k in ("notability_tag", "deletion_nomination", "orphan_tag_added", "reverted_later", "personal_life",
                      "sec_personal")}
    return t, ever


def h5_bipartite(p, h, rng):
    """Editor-page bipartite network (registered human editors). For each page: the share of women's pages among
    the other pages its editors edited (each editor's other pages weighted 1/(k-1), as in a weighted projection)."""
    e = h[(h.anon == 0) & h.user.notna() & h.qid.isin(p.index)][["user", "qid"]].drop_duplicates()
    pages = p.index.to_numpy()
    pid = pd.Series(np.arange(len(pages)), index=pages)
    uid, users = pd.factorize(e.user)
    B = sp.csr_matrix((np.ones(len(e)), (uid, pid.loc[e.qid].to_numpy())), shape=(len(users), len(pages)))
    k = np.asarray(B.sum(1)).ravel()

    def shares(f, kmax=None):
        keep = (k >= 2) if kmax is None else (k >= 2) & (k <= kmax)
        Bk = B[keep]
        w = 1.0 / (k[keep] - 1)
        F = Bk @ f
        num = Bk.T @ (w * F) - f * (Bk.T @ w)
        den = np.asarray(Bk.sum(0)).ravel()
        s = np.where(den > 0, num / np.maximum(den, 1), np.nan)
        return s

    f = p.female.to_numpy().astype(float)
    codes = strata_codes(p)

    def stat(ff, kmax=None):
        s = shares(ff, kmax)
        return np.nanmean(s[ff == 1]) - np.nanmean(s[ff == 0])

    out = {"editors": int(len(users)), "editor_page_pairs": int(len(e)),
           "editors_with_2plus_pages": int((k >= 2).sum()), "base_share_women_pages": float(f.mean())}
    s_obs = shares(f)
    out["neighbour_women_share"] = {"women_pages": float(np.nanmean(s_obs[f == 1])),
                                    "men_pages": float(np.nanmean(s_obs[f == 0]))}
    null = [stat(permute_within(f.astype(int), codes, rng).astype(float)) for _ in range(RUNS)]
    out["women_minus_men"] = perm_summary(stat(f), null)
    null100 = [stat(permute_within(f.astype(int), codes, rng).astype(float), 100) for _ in range(300)]
    out["women_minus_men_editors_with_le100_pages"] = perm_summary(stat(f, 100), null100)

    # editors who edited >= 5 pages: how many work mostly on women's pages?
    sel = k >= 5
    def focused(ff):
        return int(((B[sel] @ ff) / k[sel] >= 0.5).sum())
    nf = [focused(permute_within(f.astype(int), codes, rng).astype(float)) for _ in range(RUNS)]
    out["editors_5plus_pages"] = int(sel.sum())
    out["editors_mostly_on_womens_pages"] = perm_summary(focused(f), nf)
    return out, null, s_obs


def descriptive_links(p):
    """Descriptive only (no model): links received by creation period, from the paper's existing network."""
    try:
        from common import add_degrees, graph
        n = add_degrees(load_nodes().loc[p.index], graph(load_nodes().loc[p.index]))
        d = p.join(n[["in_degree"]])
        return d.groupby(["created_bin", "gender"]).in_degree.agg(["mean", "size"]).reset_index().to_dict("records")
    except Exception as e:
        return {"error": repr(e)[:200]}


# ------------------------------------------------------------------ figures
W = 0.8 * 8.7 / 2.54
INK, MUTED, NULLC = "#111827", "#6B7280", "#D1D5DB"
plt.rcParams.update({"font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                     "legend.fontsize": 6.5, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.linewidth": 0.6, "legend.frameon": False, "pdf.fonttype": 42})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def panel_creation(a, p):
    yr = p.groupby(["created_year", "gender"]).size().unstack(fill_value=0).reindex(range(2001, 2027), fill_value=0)
    a.bar(yr.index, yr.sum(1), color=NULLC, width=0.8, label="All new pages")
    a.set_ylabel("Pages created")
    b = a.twinx()
    share = yr.get("female", 0) / yr.sum(1).where(yr.sum(1) >= 15)      # years with < 15 new pages not drawn
    b.plot(yr.index, share * 100, "-o", color=COL["female"], ms=2.5, lw=1.3, label="Women's share")
    b.axhline(p.female.mean() * 100, color=COL["female"], lw=0.6, ls=":")
    b.set_ylabel("Women's share (%)", color=COL["female"])
    b.spines["right"].set_visible(True)
    b.tick_params(axis="y", colors=COL["female"])
    b.set_ylim(0, max(60, np.nanmax(share * 100) + 5))
    a.set_xlabel("Year the page was created")


def panel_activity(a, yearly):
    for g, lab in (("male", "Men"), ("female", "Women")):
        d = yearly[yearly.gender == g]
        a.fill_between(d.year, d.edits_per_page - 1.96 * d.se, d.edits_per_page + 1.96 * d.se, color=COL[g], alpha=.15, lw=0)
        a.plot(d.year, d.edits_per_page, "-", color=COL[g], lw=1.4, label=lab)
    a.set_xlabel("Year")
    a.set_ylabel("Human edits per existing page")
    a.legend()


def panel_lorenz(a, lorenz):
    for g, lab in (("male", "Men's pages"), ("female", "Women's pages")):
        x, c = lorenz[g]
        a.plot(x * 100, c * 100, color=COL[g], lw=1.4, label=lab)
    a.plot([0, 100], [0, 100], color=MUTED, lw=0.6, ls=":")
    a.set_xlabel("Creators, most prolific first (%)")
    a.set_ylabel("Pages created (cumulative %)")
    a.legend(loc="lower right")


def panel_types(a, t):
    t = t[t.outcome.isin(["revert", "reverted_later", "deletion_nomination", "notability_tag", "orphan_tag_added",
                          "orphan_tag_removed", "maintenance_tag", "references", "wikilinks", "categories",
                          "copyedit", "personal_life", "awards", "sec_personal", "sec_career_research",
                          "large_additions"])].sort_values("rate_ratio")
    y = np.arange(len(t))
    lo = t.rate_ratio - t.ci95.str[0]
    hi = t.ci95.str[1] - t.rate_ratio
    sig = t.p_holm < 0.05
    a.errorbar(t.rate_ratio, y, xerr=[lo, hi], fmt="none", ecolor=MUTED, lw=0.8)
    a.scatter(t.rate_ratio, y, s=14, c=np.where(sig, INK, "white"), edgecolors=INK, linewidths=0.7, zorder=3)
    a.axvline(1, color=MUTED, lw=0.6, ls=":")
    a.set_xscale("log")
    lo_x, hi_x = min(t.ci95.str[0].min(), 0.9), max(t.ci95.str[1].max(), 1.1)
    ticks = [v for v in (0.25, 0.33, 0.5, 0.67, 1, 1.5, 2, 3, 4) if lo_x * 0.9 <= v <= hi_x * 1.1]
    a.set_xticks(ticks)
    a.set_xticklabels([f"{v:g}" for v in ticks])
    a.xaxis.set_minor_formatter(plt.NullFormatter())
    a.set_yticks(y)
    a.set_yticklabels(t.label)
    a.set_xlabel("Rate ratio women / men (equal page age)")


def figures(p, yearly, traj, lorenz, types, null_bip, bip):
    for name, fn, h in (("fig4a_creation", lambda a: panel_creation(a, p), 1.9),
                        ("fig4b_activity", lambda a: panel_activity(a, yearly), 1.85),
                        ("fig4c_creators", lambda a: panel_lorenz(a, lorenz), 1.85),
                        ("fig4d_edit_types", lambda a: panel_types(a, types), 2.6)):
        fig, a = plt.subplots(figsize=(W, h), layout="constrained")
        fn(a)
        save(fig, name)

    fig, a = plt.subplots(figsize=(W, 1.7), layout="constrained")
    for g, lab in (("male", "Men"), ("female", "Women")):
        d = traj[traj.gender == g]
        a.plot(d.years_since_creation, d.median_bytes / 1000, "-o", ms=2.5, color=COL[g], lw=1.3, label=lab)
    a.set_xlabel("Years since the page was created")
    a.set_ylabel("Median page length (kB)")
    a.legend()
    save(fig, "fig4e_size_by_age")

    fig, a = plt.subplots(figsize=(W, 1.6), layout="constrained")
    a.hist(null_bip, bins=40, color=NULLC)
    a.axvline(bip["women_minus_men"]["observed"], color=COL["female"], lw=1.5)
    a.set_xlabel("Women's-page share among co-edited pages:\nwomen's pages minus men's pages")
    a.set_ylabel("Shuffled runs")
    save(fig, "fig4f_editor_network")

    fig, ax = plt.subplots(2, 2, figsize=(2 * W + 0.4, 4.4), layout="constrained")
    panel_creation(ax[0, 0], p)
    panel_activity(ax[0, 1], yearly)
    panel_lorenz(ax[1, 0], lorenz)
    panel_types(ax[1, 1], types)
    for a, l in zip(ax.ravel(), "ABCD"):
        a.text(-0.18, 1.05, l, transform=a.transAxes, fontweight="bold", fontsize=8)
    save(fig, "fig4_history")


# ------------------------------------------------------------------ summary
def fmt_rr(r):
    return f"{r['rate_ratio']:.2f} (95% CI {r['ci95'][0]:.2f}-{r['ci95'][1]:.2f})"


def write_summary(res, types):
    m = res["main"]
    c, a, cr, b = m["H1_creation"], m["H2_activity"], m["H3_creators"], m["H5_editor_network"]
    L = ["# Who Gets Remembered? Extra analysis: edit histories", "",
         "Generated by `src/r6b_history_analysis.py` from `results/rq4_history_main.json`. This analysis is an add-on:",
         "nothing in the existing results, figures or `CONCLUSIONS.md` was changed.", "",
         f"Pages: {m['n_pages']} physics/chemistry pages ({m['n_women']} women) with an edit history; "
         f"{m['n_human_edits']:,} human edits up to 13 Nov 2026 (bots removed: {m['share_bot_revisions']:.0%} of revisions).", "",
         "## H1 When were the pages created?",
         f"- Median creation year: women {c['median_created_year'].get('female'):.0f}, men {c['median_created_year'].get('male'):.0f}.",
         f"- Created in 2015 or later: women {c['share_created_2015_or_later'].get('female'):.0%}, "
         f"men {c['share_created_2015_or_later'].get('male'):.0%}.",
         f"- At equal field and birth decade, women's pages were created {c['created_year_women_minus_men']['observed']:+.1f} "
         f"years later on average (gender shuffle z = {c['created_year_women_minus_men']['z']:.1f}).", "",
         "## H2 How much are the pages edited?",
         f"- Median human edits per year since creation: women {a['median_edits_per_year'].get('female'):.1f}, "
         f"men {a['median_edits_per_year'].get('male'):.1f}.",
         f"- Rate ratio women/men at equal page age, field, decade and creation period: edits "
         f"{fmt_rr(a['rate_ratios_equal_age']['n_edits'])}; distinct editors {fmt_rr(a['rate_ratios_equal_age']['n_editors'])}.",
         f"- Same with citations added (OpenAlex-matched pages): edits "
         f"{fmt_rr(a['rate_ratios_equal_age_and_citations']['n_edits'])}.",
         f"- Median page length today: women {a['median_final_size_bytes'].get('female')/1000:.1f} kB, "
         f"men {a['median_final_size_bytes'].get('male')/1000:.1f} kB.", "",
         "## H3 Who created them?",
         f"- Share of pages created by the 10 most active creators: women {cr['top10_creators_share'].get('female'):.0%}, "
         f"men {cr['top10_creators_share'].get('male'):.0%}; if gender were shuffled within field x decade the women's "
         f"figure would be {cr['top10_share_women_if_gender_shuffled']['mean']:.0%} "
         f"(z of the difference = {cr['top10_share_women_minus_men']['z']:.1f}).",
         f"- Gini of pages per creator: women {cr['gini_pages_per_creator'].get('female'):.2f}, "
         f"men {cr['gini_pages_per_creator'].get('male'):.2f}.",
         f"- Pages created by someone who created 10 or more pages in the set: women "
         f"{cr['share_by_creators_of_10plus_pages'].get('female', 0):.0%}, men {cr['share_by_creators_of_10plus_pages'].get('male', 0):.0%}."]
    for k, v in cr.get("talk_page_templates", {}).items():
        L.append(f"- Talk page `{k.replace('talk_', '')}`: women {v['women_mean']:.1%}, men {v['men_mean']:.1%} (z = {v['z']:.1f}).")
    L += ["", "## H4 What kind of edits? (rate ratio women/men at equal page age; Holm-adjusted p)", "",
          "| Edit type | Women's pages | Men's pages | Rate ratio (95% CI) | p (Holm) |", "|---|---|---|---|---|"]
    for _, r in types.sort_values("rate_ratio").iterrows():
        L.append(f"| {r.label} | {r.women_total:,} | {r.men_total:,} | {r.rate_ratio:.2f} ({r.ci95[0]:.2f}-{r.ci95[1]:.2f}) | {r.p_holm:.3g} |")
    L += ["", "Ever happened (odds ratio women/men at equal page age):"]
    for k, v in m["H4_ever"].items():
        if "odds_ratio" in v:
            L.append(f"- {k}: women {v['women_share']:.1%}, men {v['men_share']:.1%}, OR {v['odds_ratio']:.2f} "
                     f"({v['ci95'][0]:.2f}-{v['ci95'][1]:.2f}), p = {v['p']:.3g}")
    L += ["", "## H5 Editor-page network",
          f"- {b['editors']:,} registered human editors, {b['editor_page_pairs']:,} editor-page pairs.",
          f"- Among the other pages edited by a page's editors, the share that are women's pages is "
          f"{b['neighbour_women_share']['women_pages']:.1%} for women's pages and {b['neighbour_women_share']['men_pages']:.1%} "
          f"for men's pages (base rate {b['base_share_women_pages']:.1%}); gender shuffle z = {b['women_minus_men']['z']:.1f} "
          f"(editors with <= 100 pages only: z = {b['women_minus_men_editors_with_le100_pages']['z']:.1f}).",
          f"- Editors with 5+ pages who mostly (>= 50%) edit women's pages: {b['editors_mostly_on_womens_pages']['observed']:.0f} "
          f"of {b['editors_5plus_pages']} (shuffled: {b['editors_mostly_on_womens_pages']['null_mean']:.0f}, "
          f"z = {b['editors_mostly_on_womens_pages']['z']:.1f}).", ""]
    if "biology" in res:
        bio = res["biology"]
        L += ["## Biology (check)",
              f"- Created 2015 or later: women {bio['share_created_2015_or_later'].get('female', 0):.0%}, men "
              f"{bio['share_created_2015_or_later'].get('male', 0):.0%}; edits rate ratio {fmt_rr(bio['n_edits'])}.", ""]
    L += ["## Descriptive: links received by creation period (existing network, no model)", "",
          "| Created | Gender | Mean in-degree | Pages |", "|---|---|---|---|"]
    if isinstance(m.get("descriptive_in_degree_by_creation_period"), list):
        for r in m["descriptive_in_degree_by_creation_period"]:
            L.append(f"| {r['created_bin']} | {r['gender']} | {r['mean']:.2f} | {r['size']} |")
    L += ["", "## What this measures and misses",
          "- Edit summaries are optional and free text; keyword classes are a lower bound and miss unlabelled edits.",
          "- Section names come from the automatic `/* section */` prefix; edits to the lead or with edited summaries are missed.",
          "- Bots are removed by user group and account name; semi-automated tools (AWB, Twinkle) count as human.",
          "- Creation = first revision, or the first >= 1 kB revision if the page started as a redirect.",
          "- Deleted revisions and deleted pages are not visible, so pages that were deleted are absent by construction.",
          "- Count models use robust (HC0) standard errors: the dispersion estimate collapses for some rare edit types.",
          "- Usernames are used only to count editors and creators; outputs list creators anonymised."]
    (ROOT / "HISTORY_CONCLUSIONS.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ main
def main():
    rng = np.random.default_rng(SEED)
    nodes = load_nodes()
    nodes = nodes[nodes.gender.isin(["male", "female"])]
    rv = load_revisions()
    p_all, h_all, kinds = page_table(rv, nodes)
    p_all.drop(columns=["creator"]).to_csv(RES / "rq4_history_pages.csv")      # no usernames in outputs

    res = {}
    main_set = p_all[p_all.field_group != "biology"]
    h = h_all[h_all.qid.isin(main_set.index)]
    c = h1_creation(main_set, rng)
    yearly, traj, act = h2_activity(main_set, h, rv)
    lorenz, cr = h3_creators(main_set, rng)
    types, ever = h4_edit_types(main_set, ["n_edits", "n_editors"] + kinds)
    bip, null_bip, _ = h5_bipartite(main_set, h, rng)
    res["main"] = {"n_pages": int(len(main_set)), "n_women": int(main_set.female.sum()),
                   "n_human_edits": int(len(h)),
                   "share_bot_revisions": float(rv[rv.qid.isin(main_set.index)].bot.mean()),
                   "H1_creation": c, "H2_activity": act, "H3_creators": cr,
                   "H4_ever": ever, "H5_editor_network": bip,
                   "descriptive_in_degree_by_creation_period": descriptive_links(main_set)}
    bio = p_all[p_all.field_group == "biology"]
    if bio.female.sum() >= 30:
        res["biology"] = {"n_pages": int(len(bio)),
                          "share_created_2015_or_later": bio.assign(x=bio.created_year >= 2015).groupby("gender").x.mean().to_dict(),
                          "n_edits": nb_irr(bio.assign(field_group="biology"), "n_edits")}
    (RES / "rq4_history_main.json").write_text(json.dumps(res, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    figures(main_set, yearly, traj, lorenz, types, null_bip, bip)
    write_summary(res, types[types.outcome.isin(kinds + ["n_edits", "n_editors"])])
    print((ROOT / "HISTORY_CONCLUSIONS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
