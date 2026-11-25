"""R2. RQ2 revised: are women's and men's pages written differently, once names and gender words are hidden?

Three parts.
 A. Classifier. TF-IDF + logistic regression predicts gender from the masked page text, 5-fold
    cross-validated (every page is scored by a model that never saw it). Two numbers:
      pooled AUC             can the text tell women from men at all (includes cohort and field cues)
      within-stratum AUC     only woman/man pairs from the same field x birth decade are compared,
                             so 'this reads like a young chemist' does not count
    Null: gender shuffled within field x decade, the whole cross-validation repeated (PERMS times).
    The classifier's strongest words are saved: they are an audit of what the masking let through.
 B. Distinguishing words within birth decade. The log-odds of each word (share of pages using it,
    beta-binomial shrinkage: an adaptation of Monroe et al.'s Fightin' Words to document
    frequencies, not their original model) are computed inside each field x decade cell and combined
    with inverse-variance weights. Words that only reflect women being younger drop out.
 C. Held-out replication. Words are selected on a random half of the pages and tested on the other
    half (repeated SPLITS times), so the stability check no longer reuses the data that chose the words.
Also: explicit gender mentions ('first woman', 'female physicist') from the unmasked text, with controls.
"""
import re
from collections import Counter

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from common import PROC, RES, SEED, comparison_set, load_nodes, perm_summary, permute_within, save_json

PERMS, SPLITS = 200, 100
MASKED = PROC / "text_masked"
GENDERED_ORGS = re.compile(
    r"L['’]?Or[ée]al[- ]?UNESCO|UNESCO[- ]L['’]?Or[ée]al|For GENDERWORD in Science|For Women in Science|"
    r"Association for (GENDERWORD|Women) in Science|(GENDERWORD|Women) in (Science|Physics|Chemistry|Engineering)|"
    r"Society of (GENDERWORD|Women) Engineers|(GENDERWORD|Women) Chemists Committee|Garvan[–-]Olin|"
    r"Maria Goeppert[- ]Mayer Award|Sigma Delta Epsilon|Mary Shepard B\. Upson|Agnes Fay Morgan|"
    r"Iota Sigma Pi|Committee on the Status of (GENDERWORD|Women) in Physics|CSWP|Emmy Noether Fellowship", re.I)
MASK_TOKENS = {"name", "pron", "genderword", "orgname"}
# Words the first classifier run showed still reveal gender directly (leak audit, see rq2 json):
# gender-studies vocabulary and leftovers of women-only prizes / first names the NER missed.
LEAK = set("""gender feminist feminism feminine masculine maiden nee sorority fraternity womens mens
actress heroine queen king diversity equality inclusion underrepresented stem athena swan
loreal oreal unesco garvan olin goeppert mayer noether curie marie maria meitner lise franklin rosalind
emmy mary anne anna elizabeth jane""".split())
EXPLICIT = re.compile(r"\b(first|only)\s+(woman|women|female|man|male)\b|\b(woman|female|male)\s+"
                      r"(physicist|chemist|scientist|professor|researcher)s?\b", re.I)


def tokens(s, drop=MASK_TOKENS):
    return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in drop]


def load_docs(d):
    return {q: GENDERED_ORGS.sub("ORGNAME", (MASKED / f"{q}.txt").read_text()) for q in d.index}


# ------------------------------------------------------------------ A. classifier
def within_auc(y, p, strata):
    """AUC over woman/man pairs that share a stratum (pairs pooled across strata)."""
    num = den = 0.0
    for s in np.unique(strata):
        m = strata == s
        ys, ps = y[m], p[m]
        n1, n0 = ys.sum(), (1 - ys).sum()
        if n1 and n0:
            num += roc_auc_score(ys, ps) * n1 * n0
            den += n1 * n0
    return num / den


def cv_scores(X, y, folds):
    p = np.zeros(len(y))
    for tr, te in folds:
        m = LogisticRegression(C=1.0, class_weight="balanced", solver="liblinear").fit(X[tr], y[tr])
        p[te] = m.decision_function(X[te])
    return p


def classifier(d, texts, drop, rng, perms=PERMS):
    vec = TfidfVectorizer(tokenizer=lambda s: tokens(s, drop), lowercase=False, token_pattern=None,
                          min_df=10, max_df=0.9, sublinear_tf=True)
    X = vec.fit_transform(texts)             # unsupervised: no labels used, safe to fit once
    y = d.female.to_numpy()
    strata = pd.factorize(d.stratum_fd)[0]
    folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y))
    p = cv_scores(X, y, folds)
    obs_pool, obs_within = roc_auc_score(y, p), within_auc(y, p, strata)
    null = np.empty((perms, 2))
    for i in range(perms):
        yp = permute_within(y, strata, rng)
        fp = list(StratifiedKFold(5, shuffle=True, random_state=i).split(X, yp))
        pp = cv_scores(X, yp, fp)
        # scored against the TRUE labels for 'pooled' would mix things up: both are scored on the shuffled labels
        null[i] = roc_auc_score(yp, pp), within_auc(yp, pp, strata)
    full = LogisticRegression(C=1.0, class_weight="balanced", solver="liblinear").fit(X, y)
    coef = pd.Series(full.coef_[0], index=vec.get_feature_names_out()).sort_values()
    return {"n_pages": int(len(y)), "n_features": int(X.shape[1]),
            "pooled_auc": perm_summary(obs_pool, null[:, 0]),
            "within_field_decade_auc": perm_summary(obs_within, null[:, 1]),
            "top_features_women": coef.tail(40).index.tolist()[::-1],
            "top_features_men": coef.head(40).index.tolist()}, p, null


def metadata_auc(d):
    """What gender-predictiveness is available without any text (cohort, field, impact, length)."""
    X = pd.get_dummies(d[["field_group", "birth_decade"]].astype(str)).assign(
        c=d.log_cit, w=d.log_words, dec=d.deceased).to_numpy(float)
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    y = d.female.to_numpy()
    p = cv_scores(X, y, list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y)))
    return float(roc_auc_score(y, p))


# ------------------------------------------------------------------ B/C. distinguishing words
def log_odds(docs_w, docs_m, vocab, a0=10.0):
    """Per-word log-odds difference (women - men) of the share of pages using the word, with a Beta
    prior worth a0 pseudo-pages centred on the pooled share. Returns (delta, variance)."""
    cw, cm = Counter(w for doc in docs_w for w in doc), Counter(w for doc in docs_m for w in doc)
    Nw, Nm = len(docs_w), len(docs_m)
    yw, ym = np.array([cw[w] for w in vocab], float), np.array([cm[w] for w in vocab], float)
    pi = (yw + ym) / (Nw + Nm)
    al, be = a0 * pi + 0.5, a0 * (1 - pi) + 0.5
    delta = np.log((yw + al) / (Nw - yw + be)) - np.log((ym + al) / (Nm - ym + be))
    var = 1 / (yw + al) + 1 / (Nw - yw + be) + 1 / (ym + al) + 1 / (Nm - ym + be)
    return delta, var, yw / Nw, ym / Nm


def stratified_z(d, docs, vocab, col="stratum_fd", min_each=5):
    num, den = np.zeros(len(vocab)), np.zeros(len(vocab))
    for _, s in d.groupby(col):
        w, m = s.index[s.female == 1], s.index[s.female == 0]
        if len(w) < min_each or len(m) < min_each:
            continue
        de, va, _, _ = log_odds([docs[q] for q in w], [docs[q] for q in m], vocab)
        num += de / va
        den += 1 / va
    return num / np.sqrt(den), num / den


def words(d, docsets, rng):
    all_w = Counter(w for q in d.index for w in docsets[q])
    vocab = sorted(w for w, c in all_w.items() if c >= 20)
    W, M = d.index[d.female == 1], d.index[d.female == 0]
    de, va, sw, sm_ = log_odds([docsets[q] for q in W], [docsets[q] for q in M], vocab)
    zs, ds = stratified_z(d, docsets, vocab)
    fw = pd.DataFrame({"word": vocab, "share_women": sw, "share_men": sm_, "z_pooled": de / np.sqrt(va),
                       "z_within_field_decade": zs, "log_odds_within_field_decade": ds})
    # young-vs-old contrast among MEN only: which words mark a younger biography regardless of gender
    men = d[d.female == 0]
    yo, ol = men.index[men.birth_year >= 1960], men.index[men.birth_year < 1960]
    dy, vy, _, _ = log_odds([docsets[q] for q in yo], [docsets[q] for q in ol], vocab)
    fw["z_young_vs_old_men"] = dy / np.sqrt(vy)
    fw = fw.sort_values("z_within_field_decade")
    fw.to_csv(RES / "rq2_words.csv", index=False)

    top_pooled = pd.concat([fw.nlargest(30, "z_pooled"), fw.nsmallest(30, "z_pooled")])
    keep = np.sign(top_pooled.z_pooled) == np.sign(top_pooled.z_within_field_decade)
    strong = keep & (top_pooled.z_within_field_decade.abs() > 1.96)

    # C. split-half replication of word selection
    rep_sign, rep_sig = [], []
    codes = pd.factorize(d.stratum_fd + "|" + d.female.astype(str))[0]
    for _ in range(SPLITS):
        half = np.zeros(len(d), bool)
        for c in np.unique(codes):
            ix = np.where(codes == c)[0]
            half[rng.permutation(ix)[: len(ix) // 2]] = True
        a, b = d[half], d[~half]
        za, _ = stratified_z(a, docsets, vocab, min_each=3)
        zb, _ = stratified_z(b, docsets, vocab, min_each=3)
        sel = np.r_[np.argsort(za)[:30], np.argsort(za)[-30:]]
        rep_sign.append(np.mean(np.sign(za[sel]) == np.sign(zb[sel])))
        rep_sig.append(np.mean((np.sign(za[sel]) == np.sign(zb[sel])) & (np.abs(zb[sel]) > 1.96)))
    return {"vocabulary": len(vocab),
            "top_women_within_field_decade": fw.tail(25).word.tolist()[::-1],
            "top_men_within_field_decade": fw.head(25).word.tolist(),
            "top_women_pooled": fw.nlargest(25, "z_pooled").word.tolist(),
            "top_men_pooled": fw.nsmallest(25, "z_pooled").word.tolist(),
            "pooled_top60_same_sign_within_decade": float(keep.mean()),
            "pooled_top60_still_abs_z_above_1.96_within_decade": float(strong.mean()),
            "pooled_top60_lost": top_pooled.word[~strong].tolist(),
            "split_half": {"splits": SPLITS, "top60_same_sign_in_held_out_half_mean": float(np.mean(rep_sign)),
                           "top60_same_sign_range": [float(np.min(rep_sign)), float(np.max(rep_sign))],
                           "top60_same_sign_and_abs_z_above_1.96_mean": float(np.mean(rep_sig)),
                           "chance_level_same_sign": 0.5},
            "n_words_abs_z_above_3_pooled": int((fw.z_pooled.abs() > 3).sum()),
            "n_words_abs_z_above_3_within_field_decade": int((fw.z_within_field_decade.abs() > 3).sum())}, fw


def explicit_mentions(d):
    d = d.assign(explicit=[int(bool(EXPLICIT.search((PROC / "text" / f"{q}.txt").read_text()))) for q in d.index])
    m = smf.ols("explicit ~ female + log_cit + C(field_group) + C(birth_decade) + deceased + log_words", d).fit(cov_type="HC3")
    lo, hi = m.conf_int().loc["female"]
    return {"share_women": float(d.explicit[d.female == 1].mean()), "share_men": float(d.explicit[d.female == 0].mean()),
            "adjusted_diff_pct_points": float(100 * m.params["female"]), "ci95": [float(100 * lo), float(100 * hi)]}


def main():
    rng = np.random.default_rng(SEED)
    n = load_nodes()
    d = comparison_set(n[n.main_field])
    texts = load_docs(d)
    tl = [texts[q] for q in d.index]
    out = {"metadata_only_auc": metadata_auc(d)}
    out["classifier_original_masking"], _, _ = classifier(d, tl, MASK_TOKENS, rng, perms=50)
    out["classifier_strict_masking"], p, null = classifier(d, tl, MASK_TOKENS | LEAK, rng)
    pd.DataFrame({"qid": d.index, "female": d.female.to_numpy(), "stratum": d.stratum_fd.to_numpy(),
                  "cv_score": p}).to_csv(RES / "rq2_classifier_scores.csv", index=False)
    np.save(RES / "rq2_null_draws.npy", null)
    docsets = {q: set(tokens(texts[q], MASK_TOKENS | LEAK)) for q in d.index}
    out["words"], _ = words(d, docsets, rng)
    out["explicit_gender_mentions"] = explicit_mentions(d)
    save_json(out, f"rq2_text_perms{PERMS}.json")
    return out


if __name__ == "__main__":
    o = main()
    print("metadata-only AUC", round(o["metadata_only_auc"], 3))
    for k in ("classifier_original_masking", "classifier_strict_masking"):
        c = o[k]
        print(k, "pooled", {x: round(c["pooled_auc"][x], 3) for x in ("observed", "null_mean", "z")},
              "within", {x: round(c["within_field_decade_auc"][x], 3) for x in ("observed", "null_mean", "z")})
        print("  W:", ", ".join(c["top_features_women"][:40])); print("  M:", ", ".join(c["top_features_men"][:40]))
    w = o["words"]
    for k, v in w.items():
        print(k, v)
    print(o["explicit_gender_mentions"])
