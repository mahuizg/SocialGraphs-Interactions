# Who Gets Remembered? Women scientists on Wikipedia

DTU 02805 Social Graphs and Interactions, final project.
Afonso Carvalho, Carlota Montes and María José Zamora.

Are women scientists' English Wikipedia pages less embedded in the link network between scientists'
pages than men's pages at equal citations, field and birth decade, and are the pages written differently?

## Where to start

| | |
|---|---|
| **Results** | [`pipeline_final/CONCLUSIONS.md`](pipeline_final/CONCLUSIONS.md) |
| **Notebook** (the analysis step by step, with plots) | [`pipeline_final/notebooks/who_gets_remembered_revised.ipynb`](pipeline_final/notebooks/who_gets_remembered_revised.ipynb) |
| **Paper** | [`pipeline_final/paper/`](pipeline_final/paper/) |
| **Response to the review** | [`pipeline_final/docs/RESPONSE_TO_REVIEW.md`](pipeline_final/docs/RESPONSE_TO_REVIEW.md) |
| **Page history analysis** | [`pipeline_final/HISTORY_CONCLUSIONS.md`](pipeline_final/HISTORY_CONCLUSIONS.md) |

## Repository layout

```
pipeline_final/    the final analysis (code, results, figures, notebook, paper, validation)
data_collection/   data collection (src/01-05) and the collected data that pipeline_final reads
old files/         earlier versions and working files, kept for reference (not needed to run anything)

_config.yml, _layouts/, _includes/, _posts/, assets/, index.html, posts/
                    the group's GitHub Pages site (weekly posts)
```

## Run

```bash
cd pipeline_final
pip install -r requirements.txt
./run_all.sh          # about 10 minutes, seeds fixed (2805)
```

The final analysis does not re-collect data: it reads `data_collection/data/` (set `WGR_DATA` to point elsewhere).
Data collection is `data_collection/src/01_wikidata.py` to `05_clean.py`; every query, date and record count is in
`data_collection/data/data_log.csv`. See [`pipeline_final/README.md`](pipeline_final/README.md) for every script
and its output, and [`data_collection/README.md`](data_collection/README.md) for the collection step.

---

## Group site

https://mahuizg.github.io/SocialGraphs-Interactions/

- [Week 7: Allies, enemies and the sentence behind the link](https://mahuizg.github.io/SocialGraphs-Interactions/week7-marvel-sentiment.html)

To add a post, add a Markdown file to `_posts/` named `YYYY-MM-DD-slug.md` with this front matter:

```yaml
---
title: "Post title"
week: 8
summary: "One-line summary shown on the home page card."
---
```

The layout, the styling and the card on the home page are applied automatically.
