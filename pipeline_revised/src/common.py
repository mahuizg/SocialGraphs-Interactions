"""Shared paths, data loading and helpers for the revised analysis.

The revised pipeline does NOT re-collect data. It reads the data collected by the original
pipeline (../pipeline/data, read-only) and writes everything it derives to pipeline_revised/.
Set the environment variable WGR_DATA to point somewhere else if the data folder moves.
"""
import json
import os
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DATA = Path(os.environ.get("WGR_DATA", ROOT.parent / "pipeline" / "data"))
PROC, RAW = SRC_DATA / "processed", SRC_DATA / "raw"
DATA, RES, FIG, VAL = ROOT / "data", ROOT / "results", ROOT / "figures", ROOT / "validation"
for _d in (DATA, RES, FIG, VAL):
    _d.mkdir(exist_ok=True)

SEED = 2805
COL = {"female": "#C2410C", "male": "#1D4ED8", "other": "#9CA3AF"}
EDGE_FILES = {"all": PROC / "edges_clean.csv",        # every wikilink in the wikitext (original definition)
              "prose": DATA / "edges_prose.csv"}      # links in running prose only (r0_edges_prose.py)


def save_json(obj, name):
    (RES / name).write_text(json.dumps(obj, indent=2, default=float))


def load_nodes():
    n = pd.read_csv(PROC / "nodes.csv").set_index("qid")
    n["female"] = (n.gender == "female").astype(int)
    n["deceased"] = n.deceased.fillna(0)
    n["nobel"] = n.nobel.fillna(0)
    n["log_words"] = np.log10(n.n_words)
    return n


def graph(nodes, edges="all"):
    """Directed graph on the pages in `nodes` (index = qid) for one edge definition."""
    e = pd.read_csv(EDGE_FILES[edges])
    G = nx.DiGraph()
    G.add_nodes_from(nodes.index)
    G.add_edges_from(e[e.source.isin(G) & e.target.isin(G)].itertuples(index=False))
    return G


def add_degrees(nodes, G, suffix=""):
    """in/out-degree, reciprocal links and PageRank as columns. Returns a copy."""
    n = nodes.copy()
    n["in_degree" + suffix] = pd.Series(dict(G.in_degree())).reindex(n.index).fillna(0).astype(int)
    n["out_degree" + suffix] = pd.Series(dict(G.out_degree())).reindex(n.index).fillna(0).astype(int)
    n["reciprocal" + suffix] = pd.Series({u: sum(1 for v in G.successors(u) if G.has_edge(v, u)) for u in G}
                                         ).reindex(n.index).fillna(0).astype(int)
    n["isolate" + suffix] = ((n["in_degree" + suffix] == 0) & (n["out_degree" + suffix] == 0)).astype(int)
    n["pagerank" + suffix] = pd.Series(nx.pagerank(G, alpha=0.85)).reindex(n.index)
    return n


def comparison_set(n, fields=("physics", "chemistry", "phys+chem"), bins=5, subfield_min=30):
    """Pages usable for the at-equal-impact comparison, with strata columns.

    stratum      = field x birth decade x citation quintile            (original design)
    stratum_sub  = subfield x birth decade x citation tercile          (adds OpenAlex subfield)
    Subfields with fewer than `subfield_min` pages are pooled into '<field>: other'.
    """
    d = n[n.usable & n.field_group.isin(fields) & (n.citations > 0)].copy()
    d["log_cit"] = np.log10(d.citations)
    d["cit_bin"] = pd.qcut(d.log_cit.rank(method="first"), bins, labels=False)
    d["cit_ter"] = pd.qcut(d.log_cit.rank(method="first"), 3, labels=False)
    vc = d.top_subfield.value_counts()
    d["subfield"] = np.where(d.top_subfield.map(vc).fillna(0) >= subfield_min, d.top_subfield,
                             d.top_field.fillna("unknown") + ": other")
    d["stratum"] = d.field_group + "|" + d.birth_decade.astype(str) + "|" + d.cit_bin.astype(str)
    d["stratum_sub"] = d.subfield + "|" + d.birth_decade.astype(str) + "|" + d.cit_ter.astype(str)
    d["stratum_fd"] = d.field_group + "|" + d.birth_decade.astype(str)
    return d


def permute_within(labels, codes, rng):
    """Shuffle `labels` within the groups given by integer `codes` (stratified permutation)."""
    out = labels.copy()
    order = np.argsort(codes, kind="stable")
    bounds = np.r_[0, np.cumsum(np.bincount(codes))]
    sl = labels[order]
    for a, b in zip(bounds[:-1], bounds[1:]):
        sl[a:b] = rng.permutation(sl[a:b])
    out[order] = sl
    return out


def perm_summary(obs, null):
    null = np.asarray(null)
    return {"observed": float(obs), "null_mean": float(null.mean()), "null_sd": float(null.std()),
            "null_ci95": [float(x) for x in np.percentile(null, [2.5, 97.5])],
            "z": float((obs - null.mean()) / null.std()),
            "p_two_sided": float((np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean())) + 1) / (len(null) + 1)),
            "runs": int(len(null))}
