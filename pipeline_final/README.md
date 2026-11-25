# Who Gets Remembered? Revised analysis

DTU 02805 Social Graphs and Interactions, final project. This folder is a **revision** of `../data_collection/`.
The original pipeline is untouched; nothing here writes into it. Data are read from `../data_collection/data/`.

Start with **`CONCLUSIONS.md`** (all results, generated from the result files) and the notebook
**`notebooks/who_gets_remembered_revised.ipynb`** (the same analysis step by step, with plots).
`docs/RESPONSE_TO_REVIEW.md` lists every point of the external review and what was done about it.

## Question

Are women scientists' English Wikipedia pages less embedded in the link network between scientists' pages
than men's pages at equal citations, field and birth decade, and are the pages written differently?

## What changed compared with `../data_collection/`

| | Original | Revised |
|---|---|---|
| RQ1 headline | log PageRank, "14% lower" | raw links received (in-degree) in count models, with links given, reciprocal links and isolates |
| RQ1 framing | less visible | less embedded (in both directions) |
| Strata | field × decade × citations | also subfield × decade × citations |
| Edges | every wikilink | every wikilink, and prose-only links as a second definition |
| Biology | separate "robustness" run | field × gender in one model on one network |
| RQ3 null | gender shuffled within field × decade | within link community × decade, over 10 Louvain partitions |
| RQ2 | word lists, word ranking checked on the same data | cross-validated classifier against a stratified shuffle; word ranking within birth decade with a held-out half |
| Selection | stated as a limitation | match rates, gap among unmatched pages, reweighting; name-matched sample of 601 unmatched people at equal citations |
| Validation | AI-assisted labels | second independent labelling round (AI-assisted, 18 Nov 2026) with kappa and Wilson intervals; blind sheets for a human round can still be made |
| Result files | robustness run overwrote the main run | number of shuffles is in the file name |

## Run

```bash
pip install -r requirements.txt
./run_all.sh          # ~10 minutes, seeds fixed (2805)
```

| Script | What it does | Output |
|---|---|---|
| `src/r0_edges_prose.py` | links in running prose only (no infobox, navbox, references, lists, tables) | `data/edges_prose.csv` |
| `src/r1_embeddedness.py` | RQ1: shuffles, count models, hurdle, control ladder, robustness, field × gender | `results/rq1_*` |
| `src/r2_text.py` | RQ2: classifier vs shuffle, words within decade, held-out check | `results/rq2_*` |
| `src/r3_homophily.py` | RQ3: who links to women's pages, four nulls | `results/rq3_*` |
| `src/r4_selection.py` | selection into the comparison set | `results/selection_check.json` |
| `src/r4b_openalex_namematch.py` | name-match 601 unmatched people in OpenAlex (run 18 Nov 2026 from saved responses: `--from-responses ../data/namematch_responses.json`) | `data/impact_namematch.csv` |
| `src/r4c_namematch_check.py` | data check of every accepted name match | `results/namematch_check.json`, `data/namematch_check_rows.csv` |
| `src/r5_validation.py` | `claude`: second AI round vs first (kappa, Wilson intervals, word-list recall by gender); `make`/`score`: optional human round | `results/validation_ai_vs_ai.json` (`results/validation_human.json`) |
| `src/figures.py` | the three paper figures | `figures/` |
| `src/make_summary.py` | writes `CONCLUSIONS.md` from the result files | `CONCLUSIONS.md` |

Data collection (`../data_collection/src/01`–`05`) was not repeated. Collection dates and queries are in
`../data_collection/data/data_log.csv`.

## What each measurement captures and misses

| Measurement | Captures | Misses |
|---|---|---|
| In-degree among scientists' pages | how often other scientists' biographies point to this one | links from non-biography pages (topics, institutions, prizes); readers |
| Out-degree, isolates | whether the page itself is woven into the network | why: a short or new page links less |
| Shuffle within strata | whether the gap exceeds what field, cohort and citations give by chance | anything not in the strata (page age, who wrote the page) |
| Negative binomial rate ratio | size of the gap in links, with an interval | dependence between neighbouring pages (the shuffle test and clustered SEs cover this) |
| Classifier AUC on masked text | whether the wording differs systematically | what the difference is about (content, or who wrote the page) |
| Within-decade word log-odds | which words differ beyond cohort | meaning in context; rare words |
| Share of in-links from women | same-gender linking | reasons (collaboration, shared prizes, same editors) |

## Known limits

- The comparison set is the 30% of pages with an ORCID or OpenAlex ID; matched women are younger than matched men. A name-matched sample of unmatched people gives a similar but imprecise estimate (see `CONCLUSIONS.md`).
- Citations carry their own gender gap; the estimate is the gap on top of that.
- Page creation date and creator are not in the data. Both are plausible explanations for part of RQ1 and RQ2.
- Wikidata gender is binary for all but 14 people; those pages stay in the network but not in the comparisons.
- Both labelling rounds (100 matches, 300 sentences) were AI-assisted; they agree closely but no person has checked them (see `validation/README.md`).
