"""R4b. Selection check with new data: name-match a random sample of UNMATCHED people in OpenAlex.

NOT RUN YET: the OpenAlex API was not reachable from the machine where the revision was made.
Run it on a laptop:   export OPENALEX_API_KEY=...   then   python r4b_openalex_namematch.py
then re-run r4_selection.py, which picks up data/impact_namematch.csv.

Sample: 300 women + 300 men without an ID match, physics/chemistry, stratified by birth decade.
A candidate is accepted only if (a) the OpenAlex display name matches the Wikipedia title closely,
(b) it is the only candidate that does, among authors with at least 10 works, and (c) its main field
is a natural science. Ambiguous names are dropped, not guessed. Name matching is less reliable than
ID matching: hand-check 30 accepted matches per gender before using the result.
~600 requests, 0.2 s apart, every request logged in data/data_log_revised.csv.
"""
import csv
import datetime as dt
import os
import time
from difflib import SequenceMatcher

import pandas as pd
import requests

from common import DATA, SEED, load_nodes

FIELDS_OK = {"Physics and Astronomy", "Chemistry", "Materials Science", "Engineering", "Chemical Engineering",
             "Biochemistry, Genetics and Molecular Biology", "Earth and Planetary Sciences", "Mathematics",
             "Energy", "Environmental Science"}
PER_GENDER = 300


def sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def search(name, key):
    r = requests.get("https://api.openalex.org/authors",
                     params={"search": name, "per-page": 10, "api_key": key,
                             "select": "id,display_name,works_count,cited_by_count,summary_stats,topics"},
                     timeout=60)
    r.raise_for_status()
    return r.json()["results"]


def main():
    key = os.environ["OPENALEX_API_KEY"]
    n = load_nodes()
    pool = n[n.main_field & n.gender_known & ~n.matched]
    sample = pd.concat([g.groupby("birth_decade", group_keys=False).apply(
        lambda x: x.sample(max(1, round(PER_GENDER * len(x) / len(g))), random_state=SEED))
        for _, g in pool.groupby("gender")])
    rows = []
    for qid, r in sample.iterrows():
        try:
            cands = search(r.title.split(" (")[0], key)
        except Exception as e:
            rows.append({"qid": qid, "status": f"error {e}"})
            continue
        good = []
        for c in cands:
            field = (c.get("topics") or [{}])[0].get("field", {}).get("display_name")
            if c["works_count"] >= 10 and sim(c["display_name"], r.title.split(" (")[0]) >= 0.92 and field in FIELDS_OK:
                good.append((c, field))
        if len(good) == 1:
            c, field = good[0]
            rows.append({"qid": qid, "status": "accepted", "nm_openalex_id": c["id"].rsplit("/", 1)[-1],
                         "nm_name": c["display_name"], "nm_citations": c["cited_by_count"],
                         "nm_works": c["works_count"], "nm_h_index": c["summary_stats"]["h_index"], "nm_field": field})
        else:
            rows.append({"qid": qid, "status": "no candidate" if not good else "ambiguous"})
        time.sleep(0.2)
    out = pd.DataFrame(rows).merge(sample[["title", "gender", "birth_year"]], left_on="qid", right_index=True)
    out.to_csv(DATA / "impact_namematch.csv", index=False)
    print(out.groupby(["gender", "status"]).size().unstack(fill_value=0))
    with open(DATA / "data_log_revised.csv", "a", newline="") as f:
        csv.writer(f).writerow([dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "OpenAlex API",
                                f"/authors?search=<name> for {len(sample)} unmatched people", int((out.status == "accepted").sum()),
                                "name match, selection check"])


if __name__ == "__main__":
    main()
