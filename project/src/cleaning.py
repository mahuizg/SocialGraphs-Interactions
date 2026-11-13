"""Cleaning functions (Phase 2): from the raw snapshot to the analysis tables.

Used by two things:
  - src/04_clean.py            runs every step and writes data/clean/  (the reproducible version)
  - notebooks/04_cleaning.ipynb  runs the same steps one by one so you can see what changes

Rule: flag, don't delete. Dropping a node also drops its links and changes the
network, so we only drop rows that are not a page about one scientist. Everything
else stays, with True/False columns, and each analysis filters on those.

Inputs (never edited by hand):
  data/nodes.csv, data/edges.csv, data/impact.csv, data/raw/wikidata_*.json
Human-edited inputs (created as templates the first time, never overwritten):
  data/manual/hand_check_matches.csv   verdict per checked OpenAlex match
  data/manual/birth_year_fixes.csv     correct year for people with two birth years
Outputs (data/clean/):
  nodes_clean.csv, edges_clean.csv, dropped_nodes.csv, cleaning_log.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from common import DATA, RAW

CLEAN = DATA / "clean"
MANUAL = DATA / "manual"
HAND_CHECK_FILE = MANUAL / "hand_check_matches.csv"
BIRTH_FIX_FILE = MANUAL / "birth_year_fixes.csv"

# --- Settings (write these in Methods) -------------------------------------
STUB_WORDS = 50          # pages shorter than this are stubs (kept, flagged)
SUSPECT_WORKS = 2000     # OpenAlex profiles with more works than this are suspicious
LOW_SIMILARITY = 0.5     # name similarity below this -> always hand-checked
N_RANDOM_CHECK = 85      # extra random matches to hand-check (half women)
SEED = 2805              # fixed, so the random hand-check sample never changes

IMPACT_COLS = ["match_method", "n_openalex_profiles", "openalex_id", "oa_display_name",
               "works_count", "cited_by_count", "h_index", "top_field",
               "last_institution", "name_similarity"]


# --- 0. Load ----------------------------------------------------------------
def load_raw() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(DATA / "nodes.csv")
    edges = pd.read_csv(DATA / "edges.csv")
    impact = pd.read_csv(DATA / "impact.csv")
    return nodes, edges, impact


# --- 1. Gender --------------------------------------------------------------
def clean_gender(nodes: pd.DataFrame) -> pd.DataFrame:
    """male / female / other. 'other' = multiple values, trans, non-binary, or a
    Wikidata value with no label. Nobody is removed: 'other' stays in the network
    but is left out of the women-vs-men comparisons (gender_binary = False)."""
    out = nodes.rename(columns={"gender": "gender_raw"}).copy()
    out["gender"] = np.where(out["gender_raw"].isin(["male", "female"]),
                             out["gender_raw"], "other")
    out["gender_binary"] = out["gender"].isin(["male", "female"])
    return out


# --- 2. Drop pages that are not about one scientist ----------------------------
def drop_invalid_pages(nodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two cases:
    - several people point to the same Wikipedia page (e.g. 'Family of Angela
      Merkel', the Bogdanoff twins): the text and links are not about that person;
    - the page has no text at all (soft redirects to Wikispecies)."""
    shared = nodes["wiki_title"].duplicated(keep=False)
    empty = nodes["n_words"].fillna(0) == 0
    reason = np.select([shared, empty],
                       ["page shared by several people / about someone else",
                        "no article text (soft redirect)"], default="")
    dropped = nodes.loc[reason != "", ["qid", "title", "wiki_title", "gender", "n_words"]].copy()
    dropped["reason"] = reason[reason != ""]
    return nodes.loc[reason == ""].copy(), dropped


# --- 3. Birth year, decade, field, stubs -----------------------------------------
def all_birth_years() -> dict[str, list[int]]:
    """Every birth year Wikidata gave per person (from the raw SPARQL answers)."""
    years: dict[str, set[int]] = {}
    for f in RAW.glob("wikidata_*.json"):
        for b in json.loads(f.read_text(encoding="utf-8"))["bindings"]:
            qid = b["person"]["value"].rsplit("/", 1)[-1]
            val = b.get("birth", {}).get("value", "").lstrip("+")[:4]
            if val.isdigit():
                years.setdefault(qid, set()).add(int(val))
    return {k: sorted(v) for k, v in years.items()}


def birth_fix_template(nodes: pd.DataFrame) -> pd.DataFrame:
    years = all_birth_years()
    c = nodes.loc[nodes["birth_year_conflict"], ["qid", "title", "birth_year"]].copy()
    c["years_on_wikidata"] = c["qid"].map(lambda q: ";".join(map(str, years.get(q, []))))
    c = c.rename(columns={"birth_year": "birth_year_used"})
    c["birth_year_fixed"] = pd.NA
    c["source_note"] = ""
    return c


def apply_birth_fixes(nodes: pd.DataFrame, fixes: pd.DataFrame | None) -> pd.DataFrame:
    out = nodes.copy()
    out["birth_year_fixed_by_hand"] = False
    if fixes is not None:
        f = fixes.dropna(subset=["birth_year_fixed"])
        fix_map = dict(zip(f["qid"], f["birth_year_fixed"].astype(int)))
        hit = out["qid"].isin(fix_map)
        out.loc[hit, "birth_year"] = out.loc[hit, "qid"].map(fix_map)
        out.loc[hit, "birth_year_fixed_by_hand"] = True
    # People born in 1980 go into the 1970s bin (a one-year bin would be too small).
    out["birth_decade"] = (out["birth_year"].clip(upper=1979) // 10 * 10).astype(int)
    return out


def add_field_and_stub(nodes: pd.DataFrame) -> pd.DataFrame:
    out = nodes.copy()
    out["field"] = out["fields"].map({"physicist": "physics", "chemist": "chemistry",
                                      "chemist;physicist": "both"})
    out["is_stub"] = out["n_words"] < STUB_WORDS
    return out


# --- 4. Impact ------------------------------------------------------------------------
def merge_impact(nodes: pd.DataFrame, impact: pd.DataFrame) -> pd.DataFrame:
    # nodes.csv also has an 'openalex_id' (the one written on Wikidata); keep the
    # OpenAlex profile actually used, from impact.csv.
    out = nodes.drop(columns=["openalex_id"]).merge(
        impact[["qid"] + IMPACT_COLS], on="qid", how="left")
    out["has_impact"] = out["cited_by_count"].notna()
    out["suspect_profile"] = out["works_count"] > SUSPECT_WORKS
    return out


def hand_check_template(nodes: pd.DataFrame) -> pd.DataFrame:
    """All matches with low/unknown name similarity + a fixed random sample,
    half women and half men. Fill in 'verdict' with ok / wrong / unsure."""
    m = nodes[nodes["has_impact"] & nodes["gender_binary"]]
    low = m[(m["name_similarity"] < LOW_SIMILARITY) | m["name_similarity"].isna()]
    rest = m.drop(low.index)
    half = N_RANDOM_CHECK // 2
    rnd = pd.concat([
        rest[rest["gender"] == "female"].sample(half, random_state=SEED),
        rest[rest["gender"] == "male"].sample(N_RANDOM_CHECK - half, random_state=SEED),
    ])
    s = pd.concat([low.assign(why_checked="low or unknown name similarity"),
                   rnd.assign(why_checked="random sample")])
    s["wikipedia_url"] = "https://en.wikipedia.org/wiki/" + s["wiki_title"].str.replace(" ", "_")
    s["openalex_url"] = "https://openalex.org/authors/" + s["openalex_id"]
    s["verdict"] = ""          # ok / wrong / unsure
    s["note"] = ""
    cols = ["qid", "wiki_title", "gender", "birth_year", "field", "oa_display_name",
            "name_similarity", "works_count", "cited_by_count", "top_field",
            "last_institution", "why_checked", "wikipedia_url", "openalex_url",
            "verdict", "note"]
    return s[cols].reset_index(drop=True)


def apply_hand_check(nodes: pd.DataFrame, checks: pd.DataFrame | None) -> pd.DataFrame:
    """'wrong' -> impact columns emptied (the person stays in the network)."""
    out = nodes.copy()
    out["match_checked"] = False
    out["match_ok"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    if checks is None:
        return out
    v = checks.assign(verdict=checks["verdict"].fillna("").str.strip().str.lower())
    v = v[v["verdict"].isin(["ok", "wrong", "unsure"])]
    verdict = dict(zip(v["qid"], v["verdict"]))
    hit = out["qid"].isin(verdict)
    out.loc[hit, "match_checked"] = True
    out.loc[hit, "match_ok"] = out.loc[hit, "qid"].map(verdict).map(
        {"ok": True, "wrong": False, "unsure": pd.NA})
    wrong = out["match_ok"].eq(False).fillna(False)
    out.loc[wrong, IMPACT_COLS] = np.nan
    out.loc[wrong, ["has_impact", "suspect_profile"]] = False
    return out


def add_impact_measures(nodes: pd.DataFrame) -> pd.DataFrame:
    """log citations, the main analysis set, and citation quintiles (computed once,
    pooled over women and men, on the main set only)."""
    out = nodes.copy()
    out["log_citations"] = np.log10(out["cited_by_count"] + 1)
    out["in_main_set"] = (out["gender_binary"] & out["has_impact"]
                          & ~out["match_ok"].eq(False).fillna(False)
                          & ~out["suspect_profile"].fillna(False))
    main = out["in_main_set"]
    out["citation_quintile"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[main, "citation_quintile"] = pd.qcut(
        out.loc[main, "log_citations"], 5, labels=[1, 2, 3, 4, 5]).astype(int)
    return out


# --- 5. Edges and degrees ---------------------------------------------------------------
def clean_edges(edges: pd.DataFrame, nodes: pd.DataFrame) -> pd.DataFrame:
    keep = nodes["qid"]
    e = edges[edges["source_qid"].isin(keep) & edges["target_qid"].isin(keep)]
    e = e[e["source_qid"] != e["target_qid"]].drop_duplicates(["source_qid", "target_qid"])
    return e.reset_index(drop=True)


def add_degrees(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """in_degree = number of other scientists' pages that link to this page."""
    out = nodes.copy()
    out["in_degree"] = out["qid"].map(edges["target_qid"].value_counts()).fillna(0).astype(int)
    out["out_degree"] = out["qid"].map(edges["source_qid"].value_counts()).fillna(0).astype(int)
    return out


# --- 6. Summaries -------------------------------------------------------------------------
def coverage_table(nodes: pd.DataFrame, by: str) -> pd.DataFrame:
    """Share of women and men with impact data, by birth decade or field."""
    b = nodes[nodes["gender_binary"]]
    t = b.groupby([by, "gender"]).agg(n=("qid", "size"), with_impact=("has_impact", "sum"))
    t["share"] = (t["with_impact"] / t["n"]).round(2)
    return t.unstack("gender")


def hand_check_summary(nodes: pd.DataFrame) -> pd.DataFrame:
    c = nodes[nodes["match_checked"]]
    if c.empty:
        return pd.DataFrame()
    return (c.assign(verdict=c["match_ok"].map({True: "ok", False: "wrong"}).fillna("unsure"))
             .groupby(["gender", "verdict"]).size().unstack(fill_value=0))


OUTPUT_COLS = [
    "qid", "title", "wiki_title", "revid",
    "gender", "gender_raw", "gender_binary",
    "birth_year", "birth_year_conflict", "birth_year_fixed_by_hand", "birth_decade", "field",
    "n_words", "is_stub", "in_degree", "out_degree",
    "has_impact", "match_method", "n_openalex_profiles", "openalex_id", "oa_display_name",
    "name_similarity", "match_checked", "match_ok", "suspect_profile",
    "works_count", "cited_by_count", "log_citations", "h_index", "citation_quintile",
    "top_field", "in_main_set",
]


def read_manual(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def write_template_if_missing(path: Path, df: pd.DataFrame) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return True


# --- Everything in order ----------------------------------------------------------------
def run_all(write: bool = True, verbose: bool = True) -> dict:
    """Run every step. Returns the tables and a list of (step, n_nodes, note)."""
    log: list[tuple[str, int, str]] = []
    say = print if verbose else (lambda *a, **k: None)

    nodes, edges, impact = load_raw()
    log.append(("raw nodes.csv", len(nodes), f"{len(edges)} edges"))

    nodes = clean_gender(nodes)
    n_other = int((nodes["gender"] == "other").sum())
    log.append(("gender -> male/female/other", len(nodes), f"{n_other} 'other' kept, not compared"))

    nodes, dropped = drop_invalid_pages(nodes)
    log.append(("drop shared/empty pages", len(nodes), f"{len(dropped)} dropped"))

    if write and write_template_if_missing(BIRTH_FIX_FILE, birth_fix_template(nodes)):
        say(f"Created {BIRTH_FIX_FILE.relative_to(DATA.parent)} - fill in birth_year_fixed")
    fixes = read_manual(BIRTH_FIX_FILE)
    nodes = apply_birth_fixes(nodes, fixes)
    nodes = add_field_and_stub(nodes)
    log.append(("birth decade, field, stubs", len(nodes),
                f"{int(nodes['birth_year_fixed_by_hand'].sum())} of "
                f"{int(nodes['birth_year_conflict'].sum())} birth-year conflicts fixed by hand; "
                f"{int(nodes['is_stub'].sum())} stubs (<{STUB_WORDS} words)"))

    nodes = merge_impact(nodes, impact)
    if write and write_template_if_missing(HAND_CHECK_FILE, hand_check_template(nodes)):
        say(f"Created {HAND_CHECK_FILE.relative_to(DATA.parent)} - fill in verdict")
    checks = read_manual(HAND_CHECK_FILE)
    nodes = apply_hand_check(nodes, checks)
    nodes = add_impact_measures(nodes)
    log.append(("impact merged + hand check", len(nodes),
                f"{int(nodes['has_impact'].sum())} with impact; "
                f"{int(nodes['match_checked'].sum())} checked, "
                f"{int(nodes['match_ok'].eq(False).sum())} wrong; "
                f"{int(nodes['suspect_profile'].sum())} suspect profiles (> {SUSPECT_WORKS} works)"))

    edges_c = clean_edges(edges, nodes)
    nodes = add_degrees(nodes, edges_c)
    log.append(("edges between kept nodes", len(nodes), f"{len(edges_c)} edges"))

    main = nodes[nodes["in_main_set"]]
    log.append(("main analysis set", len(main),
                f"{int((main['gender'] == 'female').sum())} women, "
                f"{int((main['gender'] == 'male').sum())} men"))

    nodes = nodes[OUTPUT_COLS].sort_values("qid").reset_index(drop=True)
    res = {"nodes": nodes, "edges": edges_c, "dropped": dropped, "log": log,
           "coverage_decade": coverage_table(nodes, "birth_decade"),
           "coverage_field": coverage_table(nodes, "field"),
           "hand_check": hand_check_summary(nodes)}
    if write:
        write_outputs(res)
        say(f"Wrote data/clean/ ({len(nodes)} nodes, {len(edges_c)} edges)")
    return res


def write_outputs(res: dict) -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    res["nodes"].to_csv(CLEAN / "nodes_clean.csv", index=False, encoding="utf-8")
    res["edges"].to_csv(CLEAN / "edges_clean.csv", index=False, encoding="utf-8")
    res["dropped"].to_csv(CLEAN / "dropped_nodes.csv", index=False, encoding="utf-8")
    (CLEAN / "cleaning_log.md").write_text(cleaning_log_md(res), encoding="utf-8")


def _md(df: pd.DataFrame, index: bool = True) -> str:
    """Small markdown table writer (avoids needing the 'tabulate' package)."""
    d = df.copy()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = [" ".join(map(str, c)) for c in d.columns]
    if index:
        d = d.reset_index()
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "---|" * len(d.columns)
    rows = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |"
            for r in d.itertuples(index=False)]
    return "\n".join([head, sep] + rows)


def cleaning_log_md(res: dict) -> str:
    n = res["nodes"]
    lines = ["# Cleaning log", "",
             "Generated by `src/04_clean.py` - do not edit by hand.", "",
             "## Steps", "", "| Step | Nodes | Note |", "|---|---|---|"]
    lines += [f"| {s} | {k:,} | {note} |" for s, k, note in res["log"]]
    lines += ["", "## Dropped pages", "", _md(res["dropped"], index=False), "",
              "## Gender (raw Wikidata value -> cleaned)", "",
              _md(n.groupby(["gender", "gender_raw"]).size().rename("n").reset_index(),
                  index=False), "",
              "## Impact coverage by birth decade (share with OpenAlex data)", "",
              _md(res["coverage_decade"]), "",
              "## Impact coverage by field", "", _md(res["coverage_field"]), ""]
    hc = res["hand_check"]
    lines += ["## Hand check of OpenAlex matches", "",
              _md(hc) if not hc.empty else "Not done yet (no verdicts in "
              "`data/manual/hand_check_matches.csv`).", "",
              "## Settings", "",
              f"- stub: fewer than {STUB_WORDS} words",
              f"- suspect OpenAlex profile: more than {SUSPECT_WORKS} works",
              f"- always hand-checked: name similarity below {LOW_SIMILARITY} or unknown",
              f"- random hand-check sample: {N_RANDOM_CHECK} (half women), seed {SEED}",
              "- birth decade: 1980 counted in the 1970s",
              "- citation quintiles: log10(citations + 1), pooled over women and men, main set only",
              "- main set: male or female, has impact, not a wrong match, not a suspect profile"]
    return "\n".join(lines) + "\n"
