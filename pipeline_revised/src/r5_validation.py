"""R5. Human validation sheets and agreement scores.

The first round of quality checks (100 OpenAlex matches, 300 sentences) was labelled with AI help.
That is circular: a model checked a model. This script prepares BLIND sheets for two people and
scores them once they are filled in.

  python r5_validation.py make     writes validation/*_labeller_A.csv and *_labeller_B.csv
                                   (no AI labels, no gender, no strata, different row order per person)
  python r5_validation.py score    human-human Cohen's kappa, human-vs-AI kappa, match accuracy with
                                   Wilson 95% intervals by gender, and the test of equal accuracy

Fill in 1 or 0. Matches: `correct` (same person?) and `profile_complete` (does the OpenAlex profile
look like the whole career?). Sentences: `is_personal` (family, marriage, children, private life)
and `is_professional` (research, jobs, degrees, prizes). A sentence can be both or neither.
About an hour per person. Do not look at each other's sheet or at the AI labels first.
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from sklearn.metrics import cohen_kappa_score

from common import PROC, ROOT, SEED, VAL, save_json

AI_MATCH = PROC / "handcheck_sample.csv"
AI_SENT = ROOT.parent / "pipeline" / "results" / "sentences_to_label.csv"


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


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
