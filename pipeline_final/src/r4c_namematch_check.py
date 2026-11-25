"""R4c. Check of the name matches accepted by r4b, before they are used in r4_selection.py.

r4b asks for a hand check of about 30 accepted matches per gender. Here ALL accepted matches are checked from data, with
the same rule as the second validation round of the ID matches (validation/README.md):
  correct = the OpenAlex display name contains the Wikipedia surname (letters only, accents stripped)
            AND at least 2 distinct content words from the profile's top-5 OpenAlex topics appear in the page's wikitext.
Topic words come from data/namematch_topic_words.json (fetched 18 Nov 2026). This is a data rule, not a person looking at
both pages: it misses wrong matches in the same field and fails right matches whose page says little about the research.
Matches that fail it are listed for a person to open, and r4_selection.py reports the model with and without them.

  python r4c_namematch_check.py      -> results/namematch_check.json, data/namematch_check_rows.csv
"""
import re
import unicodedata

import numpy as np
import pandas as pd

from common import DATA, RAW, save_json
from r5_validation import wilson

GENERIC = set("""research studies study analysis analyses applications application theory theories methods method systems
system techniques technique development performance advanced related their with from and based using effects effect
properties property processes process modeling modelling models model various other into chemical physical physics
chemistry science sciences""".split())


def norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def topic_words(topics):
    return {w for w in re.findall(r"[a-z]{4,}", norm(topics)) if w not in GENERIC}


def letters(s):
    return re.sub(r"[^a-z]", "", norm(s))


def main():
    import json
    nm = pd.read_csv(DATA / "impact_namematch.csv")
    tw = json.loads((DATA / "namematch_topic_words.json").read_text(encoding="utf-8"))
    acc = nm[nm.status == "accepted"].copy()
    rows = []
    for _, r in acc.iterrows():
        f = RAW / "wikitext" / f"{r.qid}.wiki"
        text = norm(f.read_text(encoding="utf-8", errors="ignore")) if f.exists() else ""
        surname = letters(r.title.split(" (")[0].split()[-1])
        words = set(tw[r.nm_openalex_id].split())
        found = sorted(w for w in words if re.search(rf"\b{w}", text))
        ok_name = surname in letters(r.nm_name)
        rows.append({"qid": r.qid, "title": r.title, "gender": r.gender, "nm_name": r.nm_name,
                     "openalex_url": f"https://openalex.org/{r.nm_openalex_id}",
                     "wikipedia_url": "https://en.wikipedia.org/wiki/" + r.title.replace(" ", "_"),
                     "surname_in_name": ok_name, "topic_words": len(words), "topic_words_found": len(found),
                     "found": " ".join(found), "wikitext_found": bool(text),
                     "correct": int(ok_name and len(found) >= 2)})
    d = pd.DataFrame(rows)
    d.to_csv(DATA / "namematch_check_rows.csv", index=False)
    out = {"rule": ("correct = OpenAlex display name contains the Wikipedia surname AND >= 2 distinct content words from "
                    "the top-5 OpenAlex topics appear in the wikitext; checked from data, not by a person"),
           "checked": len(d), "by_gender": {}}
    for g in ("female", "male"):
        x = d[d.gender == g]
        k, n = int(x.correct.sum()), len(x)
        out["by_gender"][g] = {"k": k, "n": n, "share": k / n if n else None, "wilson95": wilson(k, n) if n else None}
    out["failed"] = d.loc[d.correct == 0, ["qid", "title", "nm_name", "topic_words_found", "found"]].to_dict("records")
    save_json(out, "namematch_check.json")
    print({g: (v["k"], v["n"]) for g, v in out["by_gender"].items()})
    print(pd.DataFrame(out["failed"]).to_string())


if __name__ == "__main__":
    main()
