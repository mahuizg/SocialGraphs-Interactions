"""R3. RQ3 revised: do women's pages get a larger share of their in-links from women than expected?

Statistic: share of in-links to women's pages that come from women's pages (network fixed).
The original null shuffled gender within field x birth decade. That leaves topical clustering in
the statistic: if women are concentrated in some link communities, links inside those communities
are woman-to-woman more often without any gender preference in linking.

Nulls compared here (gender labels shuffled, network fixed, RUNS shuffles each):
  field x decade                (original)
  community                     (Louvain on the undirected graph)
  community x decade            (the revised null asked for in the review)
  community x decade x field
Louvain partitions change with the seed, so the community nulls are repeated over SEEDS partitions
and we report the range. Cells with a single gender cannot be shuffled; we report how many women
sit in cells where shuffling can change something, because a null with no freedom always 'agrees'
with the data.
"""
import networkx as nx
import numpy as np
import pandas as pd

from common import SEED, graph, load_nodes, perm_summary, permute_within, save_json

RUNS, SEEDS = 1000, 10


def main():
    rng = np.random.default_rng(SEED)
    n = load_nodes()
    n = n[n.main_field]
    G = graph(n, "all")
    k = n[n.gender_known]
    idx = {q: i for i, q in enumerate(k.index)}
    E = np.array([(idx[u], idx[v]) for u, v in G.edges() if u in idx and v in idx])
    fem = k.female.to_numpy()
    U = G.to_undirected()
    linked = np.zeros(len(fem), bool)
    linked[np.unique(E)] = True

    def stat(f):
        to_w = f[E[:, 1]] == 1
        return f[E[to_w, 0]].mean()

    def null(codes, runs=RUNS):
        return np.array([stat(permute_within(fem, codes, rng)) for _ in range(runs)])

    def freedom(codes):
        # only pages with at least one link matter for the statistic (isolated pages have no edges)
        t = pd.crosstab(codes[linked], fem[linked])
        mixed = (t[0] > 0) & (t[1] > 0)
        return {"cells_with_linked_pages": int(len(t)), "linked_women_in_mixed_cells": int(t[1][mixed].sum()),
                "share_women_in_mixed_cells": float(t[1][mixed].sum() / t[1].sum())}

    obs = stat(fem)
    out = {"graph": {"nodes": G.number_of_nodes(), "edges_between_gender_known": int(len(E))},
           "observed_share_from_women": float(obs),
           "share_women_among_all_linking_pages": float(fem[E[:, 0]].mean()),
           "women_to_women_edges": int(((fem[E[:, 0]] == 1) & (fem[E[:, 1]] == 1)).sum()),
           "edges_to_women": int((fem[E[:, 1]] == 1).sum())}

    fd = pd.factorize(k.field_group + "|" + k.birth_decade.astype(str))[0]
    out["null_field_x_decade"] = {**perm_summary(obs, null(fd)), **freedom(fd)}

    per_seed, comm_tables = [], None
    for s in range(SEEDS):
        parts = nx.community.louvain_communities(U, seed=s)
        comm = {q: i for i, c in enumerate(parts) for q in c}
        c = k.index.map(comm).to_numpy()
        row = {"seed": s, "communities_ge_100": int(sum(len(p) >= 100 for p in parts))}
        for name, codes in (("community", pd.factorize(c)[0]),
                            ("community_x_decade", pd.factorize(pd.Series(c).astype(str) + "|" + k.birth_decade.astype(str).to_numpy())[0]),
                            ("community_x_decade_x_field", pd.factorize(pd.Series(c).astype(str) + "|" + k.birth_decade.astype(str).to_numpy() + "|" + k.field_group.to_numpy())[0])):
            r = {**perm_summary(obs, null(codes, 300 if s else RUNS)), **freedom(codes)}
            row[name] = r
        per_seed.append(row)
        if s == 0:
            t = k.assign(community=c)
            big = t.community.value_counts()
            big = big[big >= 100].index
            comm_tables = (t[t.community.isin(big)].groupby("community")
                           .agg(size=("female", "size"), share_women=("female", "mean"),
                                median_birth=("birth_year", "median"),
                                hub=("n_links_all", lambda x: t.loc[x.index, "title"].iloc[0]))
                           .sort_values("size", ascending=False))
            pr = pd.Series(nx.pagerank(G))
            comm_tables["hub"] = [t[t.community == ci].index.map(pr).to_series().pipe(
                lambda v: t.loc[t[t.community == ci].index[np.argmax(v.to_numpy())], "title"]) for ci in comm_tables.index]
    out["by_louvain_seed"] = per_seed
    for name in ("community", "community_x_decade", "community_x_decade_x_field"):
        zs = [r[name]["z"] for r in per_seed]
        nm = [r[name]["null_mean"] for r in per_seed]
        out[f"summary_{name}"] = {"null_mean_range": [min(nm), max(nm)], "null_mean_avg": float(np.mean(nm)),
                                  "z_range": [min(zs), max(zs)], "z_median": float(np.median(zs)),
                                  "seeds_with_abs_z_above_2": int(sum(abs(z) > 2 for z in zs)),
                                  "share_women_in_mixed_cells_avg": float(np.mean(
                                      [r[name]["share_women_in_mixed_cells"] for r in per_seed]))}
    out["communities_seed0_ge100"] = comm_tables.round(3).reset_index().to_dict("records")
    out["share_women_range_in_communities_ge100"] = [float(comm_tables.share_women.min()),
                                                     float(comm_tables.share_women.max())]
    np.save(__import__("common").RES / "rq3_null_draws.npy",
            np.vstack([null(fd), null(pd.factorize(pd.Series(k.index.map(
                {q: i for i, c in enumerate(nx.community.louvain_communities(U, seed=0)) for q in c})).astype(str)
                + "|" + k.birth_decade.astype(str).to_numpy())[0])]))
    save_json(out, f"rq3_homophily_runs{RUNS}.json")
    return out


if __name__ == "__main__":
    o = main()
    print("observed", o["observed_share_from_women"], "W->W edges", o["women_to_women_edges"], "of", o["edges_to_women"])
    print("field x decade", {k: o["null_field_x_decade"][k] for k in ("null_mean", "z", "share_women_in_mixed_cells")})
    for nme in ("community", "community_x_decade", "community_x_decade_x_field"):
        print(nme, o[f"summary_{nme}"])
    print(pd.DataFrame(o["communities_seed0_ge100"]).to_string())
