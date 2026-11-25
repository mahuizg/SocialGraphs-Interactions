"""R5. Human validation sheets and agreement scores.

The first round of quality checks (100 OpenAlex matches, 300 sentences) was labelled with AI help.
That is circular: a model checked a model. This script prepares BLIND sheets for two people and
scores them once they are filled in.

  python r5_validation.py make     writes validation/*_labeller_A.csv and *_labeller_B.csv
                                   (no AI labels, no gender, no strata, different row order per person)
  python r5_validation.py score    human-human Cohen's kappa, human-vs-AI kappa, match accuracy with
                                   Wilson 95% intervals by gender, and the test of equal accuracy
  python r5_validation.py claude   scores the second AI pass (validation/matches_labeller.csv and
                                   validation/sentences_labeller.csv, filled in by Claude on 18 Nov 2026;
                                   *_labeller_claude.csv is also accepted) against the first AI-assisted pass,
                                   and re-estimates the precision/recall of the personal and professional word
                                   lists by gender with the second-pass labels. This is AI-vs-AI agreement: it
                                   shows the labels are stable, NOT that a human checked them. Report it as such.

Fill in 1 or 0. Matches: `correct` (same person?) and `profile_complete` (does the OpenAlex profile
look like the whole career?). Sentences: `is_personal` (family, marriage, children, private life)
and `is_professional` (research, jobs, degrees, prizes). A sentence can be both or neither.
About an hour per person. Do not look at each other's sheet or at the AI labels first.
"""
import ast
import json
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from sklearn.metrics import cohen_kappa_score

from common import PROC, ROOT, SEED, VAL, save_json

AI_MATCH = PROC / "handcheck_sample.csv"
AI_SENT = ROOT.parent / "data_collection" / "results" / "sentences_to_label.csv"
TEXT_SRC = ROOT.parent / "data_collection" / "src" / "07_text.py"      # where the personal/professional word lists live


def second_pass_sheet(name):
    """The second-pass (Claude) sheet: *_labeller_claude.csv if present, else *_labeller.csv."""
    for f in (VAL / f"{name}_labeller_claude.csv", VAL / f"{name}_labeller.csv"):
        if f.exists():
            return f
    raise FileNotFoundError(f"no second-pass sheet for {name} in {VAL}")


def word_lists():
    """PERSONAL and PROFESSIONAL exactly as defined in ../data_collection/src/07_text.py (read, not imported:
    importing it would clash with this folder's common.py)."""
    tree = ast.parse(TEXT_SRC.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if isinstance(n, ast.Assign)
            and any(getattr(t, "id", None) in ("PERSONAL", "PROFESSIONAL") for t in n.targets)]
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(TEXT_SRC), "exec"), ns)
    return ns["PERSONAL"], ns["PROFESSIONAL"]


def tokens(s):  # same tokeniser as ../data_collection/src/07_text.py
    return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in {"name", "pron", "genderword", "orgname"}]


def word_list_accuracy(L, B=1000):
    """Weighted precision and recall of each word list, overall and by gender, with the same estimator as
    ../data_collection/src/07_text.py (weights = stratum population / stratum sample size), plus a bootstrap
    (within gender x stratum cells) for the women-minus-men recall difference."""
    PERSONAL, PROFESSIONAL = word_lists()
    rng = np.random.default_rng(SEED)
    has_prof = L.sentence.map(lambda s: bool(set(tokens(s)) & PROFESSIONAL))
    out = {}
    for lst, flag_strata, col in (("personal", {"personal_flag"}, "is_personal"),
                                  ("professional", {"professional_flag"}, "is_professional")):
        def est(df):
            w = df.stratum_pop / df.groupby(["gender", "stratum"]).stratum.transform("size")
            pos = df[col].astype(int)
            flagged = df.stratum.isin(flag_strata)
            if lst == "professional":
                flagged = flagged | has_prof.loc[df.index]
            tp = (w * pos * flagged).sum()
            return tp / max((w * flagged).sum(), 1e-9), tp / max((w * pos).sum(), 1e-9)

        def by_gender(df):
            return {g: est(df[df.gender == g]) for g in ("female", "male")}

        p, r = est(L)
        bg = by_gender(L)
        cells = [idx.to_numpy() for idx in L.groupby(["gender", "stratum"]).groups.values()]
        diffs = []
        for _ in range(B):
            d = L.loc[np.concatenate([rng.choice(c, len(c), replace=True) for c in cells])]
            x = by_gender(d)
            diffs.append(x["female"][1] - x["male"][1])
        out[lst] = {"precision": float(p), "recall": float(r),
                    "precision_female": float(bg["female"][0]), "recall_female": float(bg["female"][1]),
                    "precision_male": float(bg["male"][0]), "recall_male": float(bg["male"][1]),
                    "recall_diff_women_minus_men": float(bg["female"][1] - bg["male"][1]),
                    "recall_diff_ci95": np.percentile(diffs, [2.5, 97.5]).tolist()}
    return out


def wilson(k, n, z=1.96):
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(c - h), float(c + h)]


def make():
    m, s = pd.read_csv(AI_MATCH), pd.read_csv(AI_SENT)
    for i, who in enumerate("AB"):
        a = m[["qid", "title", "birth_year", "field", "oa_name", "wikipedia_url", "openalex_url"]].sample(
            frac=1, random_state=SEED + i).assign(correct="", profile_complete="", comment="")
        b = s[["qid", "sent_idx", "sentence"]].sample(frac=1, random_state=SEED + 10 + i).assign(
            is_personal="", is_professional="")
        for df, name in ((a, "matches"), (b, "sentences")):
            f = VAL / f"{name}_labeller_{who}.csv"
            if f.exists():
                print(f"{f.name} exists: not overwritten (may contain labels)")
            else:
                df.to_csv(f, index=False)
                print("wrote", f.name, len(df))


def score():
    out = {}
    for name, key, cols, ai in (("matches", ["qid"], ["correct", "profile_complete"], pd.read_csv(AI_MATCH)),
                                ("sentences", ["qid", "sent_idx"], ["is_personal", "is_professional"], pd.read_csv(AI_SENT))):
        A = pd.read_csv(VAL / f"{name}_labeller_A.csv").set_index(key)
        B = pd.read_csv(VAL / f"{name}_labeller_B.csv").set_index(key).reindex(A.index)
        ai = ai.set_index(key).reindex(A.index)
        res = {}
        for c in cols:
            ok = A[c].notna() & B[c].notna()
            if not ok.any():
                res[c] = "not labelled yet"
                continue
            a, b, x = A.loc[ok, c].astype(int), B.loc[ok, c].astype(int), ai.loc[ok, c].astype(int)
            res[c] = {"n": int(ok.sum()), "agreement_A_B": float((a == b).mean()),
                      "kappa_A_B": float(cohen_kappa_score(a, b)) if a.nunique() + b.nunique() > 2 else None,
                      "kappa_A_vs_AI": float(cohen_kappa_score(a, x)) if a.nunique() + x.nunique() > 2 else None,
                      "agreement_A_vs_AI": float((a == x).mean()), "positive_share_A": float(a.mean())}
            if name == "matches":
                g = ai.loc[ok, "gender"]
                both = ((a == 1) & (b == 1)).astype(int)        # counted correct only if both people agree
                by = {k: {"k": int(both[g == k].sum()), "n": int((g == k).sum())} for k in ("female", "male")}
                for k in by:
                    by[k]["share"], by[k]["wilson95"] = by[k]["k"] / by[k]["n"], wilson(by[k]["k"], by[k]["n"])
                t = [[by[k]["k"], by[k]["n"] - by[k]["k"]] for k in ("female", "male")]
                res[c]["by_gender"] = by
                res[c]["fisher_p_women_vs_men"] = float(fisher_exact(t)[1])
                res[c]["note"] = ("With 50 per gender a difference in accuracy smaller than roughly 10 points "
                                  "cannot be detected: report the intervals, not 'no bias'.")
        out[name] = res
    save_json(out, "validation_human.json")
    print(pd.Series(out).to_string())


def claude():
    """Second AI pass vs first AI-assisted pass (AI vs AI, not human validation)."""
    ai_m, ai_s = pd.read_csv(AI_MATCH).set_index("qid"), pd.read_csv(AI_SENT).set_index(["qid", "sent_idx"])
    fm, fs = second_pass_sheet("matches"), second_pass_sheet("sentences")
    cm = pd.read_csv(fm).set_index("qid").reindex(ai_m.index)
    cs = pd.read_csv(fs).set_index(["qid", "sent_idx"]).reindex(ai_s.index)
    assert cm[["correct", "profile_complete"]].notna().all().all(), f"{fm.name} has unlabelled rows"
    assert cs[["is_personal", "is_professional"]].notna().all().all(), f"{fs.name} has unlabelled rows"
    out = {"what": "AI vs AI: second pass (Claude, 18 Nov 2026) against the first AI-assisted pass. Not human validation.",
           "how_matches_were_checked": ("correct = OpenAlex display name or alias contains the Wikipedia surname AND at "
                                        "least 2 words from the profile's top-5 OpenAlex topics appear in the Wikipedia "
                                        "wikitext; profile_complete = at least 1 OpenAlex work per career year since age 25"),
           "caveat_sentences": "the second labeller had seen the first-pass labels before labelling, so it is not blind",
           "files": {"first_pass_matches": str(AI_MATCH.relative_to(ROOT.parent)),
                     "first_pass_sentences": str(AI_SENT.relative_to(ROOT.parent)),
                     "second_pass_matches": f"pipeline_final/validation/{fm.name}",
                     "second_pass_sentences": f"pipeline_final/validation/{fs.name}"}}
    for name, ref, new, cols in (("matches", ai_m, cm, ["correct", "profile_complete"]),
                                 ("sentences", ai_s, cs, ["is_personal", "is_professional"])):
        res = {}
        for c in cols:
            a, b = ref[c].astype(int), new[c].astype(int)
            res[c] = {"n": int(len(a)), "agreement": float((a == b).mean()),
                      "kappa": float(cohen_kappa_score(a, b)) if a.nunique() + b.nunique() > 2 else None,
                      "positive_first_pass": int(a.sum()), "positive_second_pass": int(b.sum())}
            if name == "matches":
                g = ref["gender"]
                res[c]["by_gender_second_pass"] = {k: {"k": int(b[g == k].sum()), "n": int((g == k).sum()),
                                                       "wilson95": wilson(int(b[g == k].sum()), int((g == k).sum()))}
                                                   for k in ("female", "male")}
        out[name] = res
    # The personal/professional word lists were dropped from RQ2 because the first-pass labels showed they find
    # personal sentences far more often on women's pages. Re-estimate that with the second-pass labels.
    L1 = ai_s.reset_index()
    L2 = L1.drop(columns=["is_personal", "is_professional"]).merge(
        cs[["is_personal", "is_professional"]].reset_index(), on=["qid", "sent_idx"])
    out["word_lists"] = {"note": ("Stratum-weighted precision/recall of the word lists in ../data_collection/src/07_text.py. "
                                  "Recall differing by gender is why the lists were dropped from RQ2."),
                         "first_pass_labels": word_list_accuracy(L1), "second_pass_labels": word_list_accuracy(L2)}
    save_json(out, "validation_ai_vs_ai.json")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"make": make, "score": score, "claude": claude}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
