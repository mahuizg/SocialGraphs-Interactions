"""R4b. Selection check with new data: name-match a random sample of UNMATCHED people in OpenAlex.

Run on a laptop:   export OPENALEX_API_KEY=...   then   python r4b_openalex_namematch.py
then re-run r4_selection.py, which picks up data/impact_namematch.csv.

RUN ON 18 NOV 2026 via saved responses: api.openalex.org was blocked from the analysis machine, so the same 601 searches
(same sample, same parameters) were made from a browser on 18 Nov 2026, and every candidate that could pass the rule
(>= 10 works, an accepted field, name similarity >= 0.92 computed with an exact JavaScript port of difflib) was saved to
data/namematch_responses.json. Then
    python r4b_openalex_namematch.py --from-responses ../data/namematch_responses.json
applies exactly the rule below (similarity recomputed here with difflib) and writes the same output. The saved file also
holds the top-5 OpenAlex topics of the near-exact candidates of a random 50 people per gender, used by the check of
accepted matches (r4c_namematch_check.py).

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


def draw_sample():
    n = load_nodes()
    pool = n[n.main_field & n.gender_known & ~n.matched]
    return pd.concat([g.groupby("birth_decade", group_keys=False).apply(
        lambda x: x.sample(max(1, round(PER_GENDER * len(x) / len(g))), random_state=SEED))
        for _, g in pool.groupby("gender")])


def decide(qid, name, cands):
    """cands: dicts with id, display_name, works_count, cited_by_count, h_index, field. The acceptance rule."""
    good = [c for c in cands
            if c["works_count"] >= 10 and sim(c["display_name"], name) >= 0.92 and c["field"] in FIELDS_OK]
    if len(good) == 1:
        c = good[0]
        return {"qid": qid, "status": "accepted", "nm_openalex_id": c["id"].rsplit("/", 1)[-1],
                "nm_name": c["display_name"], "nm_citations": c["cited_by_count"], "nm_works": c["works_count"],
                "nm_h_index": c["h_index"], "nm_field": c["field"], "nm_similarity": round(sim(c["display_name"], name), 4),
                "nm_topics": c.get("topics", "")}
    return {"qid": qid, "status": "no candidate" if not good else "ambiguous"}


def write(rows, sample, source):
    out = pd.DataFrame(rows).merge(sample[["title", "gender", "birth_year"]], left_on="qid", right_index=True)
    out.to_csv(DATA / "impact_namematch.csv", index=False)
    print(out.groupby(["gender", "status"]).size().unstack(fill_value=0))
    with open(DATA / "data_log_revised.csv", "a", newline="") as f:
        csv.writer(f).writerow([dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), source,
                                f"/authors?search=<name> for {len(sample)} unmatched people", int((out.status == "accepted").sum()),
                                "name match, selection check"])


def main():
    key = os.environ["OPENALEX_API_KEY"]
    sample = draw_sample()
    rows = []
    for qid, r in sample.iterrows():
        name = r.title.split(" (")[0]
        try:
            res = search(name, key)
        except Exception as e:
            rows.append({"qid": qid, "status": f"error {e}"})
            continue
        cands = [{"id": c["id"], "display_name": c["display_name"], "works_count": c["works_count"],
                  "cited_by_count": c["cited_by_count"], "h_index": c["summary_stats"]["h_index"],
                  "field": (c.get("topics") or [{}])[0].get("field", {}).get("display_name")} for c in res]
        rows.append(decide(qid, name, cands))
        time.sleep(0.2)
    write(rows, sample, "OpenAlex API")


def from_responses(path):
    """Same rule, applied to responses saved from a browser (format: {qid: {"n": k, "c": [[id, name, citations,
    works, h_index, field, js_similarity, topics], ...]} or {"err": msg}})."""
    import json
    saved = json.loads(open(path, encoding="utf-8").read())
    meta = saved.pop("_meta", {})
    sample = draw_sample()
    missing = set(sample.index) - set(saved)
    assert not missing, f"{len(missing)} sampled people have no saved response"
    rows = []
    for qid, r in sample.iterrows():
        v = saved[qid]
        if "err" in v:
            rows.append({"qid": qid, "status": f"error {v['err']}"})
            continue
        cands = [{"id": c[0], "display_name": c[1], "cited_by_count": c[2], "works_count": c[3], "h_index": c[4],
                  "field": c[5], "topics": c[7]} for c in v["c"]]
        rows.append(decide(qid, r.title.split(" (")[0], cands))
    write(rows, sample, f"OpenAlex API via browser, {meta.get('started', '')} to {meta.get('finished', '')}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--from-responses":
        from_responses(sys.argv[2])
    else:
        main()
