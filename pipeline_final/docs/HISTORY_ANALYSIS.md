# Extra analysis: edit histories of the scientists' pages

This analysis is an **add-on**. It does not modify, re-run or overwrite anything that already exists in
`data_collection/` or `pipeline_final/` (results, figures, `CONCLUSIONS.md`, `run_all.sh`, the paper). It only
reads `../data_collection/data/processed/nodes.csv` and `edges_clean.csv`, and writes new files with new names.

## Questions

| | Question | Main measure |
|---|---|---|
| H1 | When were women's and men's pages created? | women's share of new pages per year; creation year at equal field x birth decade (gender shuffle) |
| H2 | How much are they edited over the years? | human edits and editors per page per calendar year; rate ratio at equal page age; page length over time |
| H3 | Who created them? | concentration of creators (top-10 share, Gini, Lorenz curve); WikiProject / Articles for creation / Old AfD banners on talk pages |
| H4 | What kind of edits? | edit summaries and edited sections classified (reverts, deletion / notability / orphan tags, references, links, categories, personal life, awards, career) -> rate ratios women/men at equal page age, Holm-corrected |
| H5 | Are women's pages edited by the same people? | editor-page bipartite network: share of women's pages among co-edited pages vs gender shuffle; editors who mostly edit women's pages |

Main set = the paper's network (physics, chemistry, phys+chem); biology is repeated as a check.

## Run (from `pipeline_final/src`, on a machine with internet access)

```bash
set WGR_CONTACT=sXXXXXX@student.dtu.dk        # Windows (PowerShell: $env:WGR_CONTACT="...")
python r6a_history_collect.py --limit 50      # quick test, ~1 min
python r6a_history_collect.py                 # all ~12,400 pages, ~1-2 h, resumable (Ctrl+C and re-run)
python r6b_history_analysis.py                # ~2-5 min
```

## Outputs (all new)

| File | Content |
|---|---|
| `data/history/revisions/part_*.jsonl.gz` | revision metadata per page (not committed to git: usernames, size) |
| `data/history/bots.json`, `talk_templates.csv`, `collect_log.csv` | bot accounts, talk-page banners, query log |
| `results/rq4_history_main.json` | every number in `HISTORY_CONCLUSIONS.md` |
| `results/rq4_history_*.csv` | per-page table (no usernames), edits by year, page length by age, edit-type models, creations by year |
| `figures/history/fig4_history.pdf` | 2 x 2 figure: A creation timing, B edits over the years, C creator concentration, D edit types |
| `figures/history/fig4a-f_*.pdf` | one panel per file (column width), plus page length (e) and editor network null (f) |
| `HISTORY_CONCLUSIONS.md` | results written out from the JSON |

## Limits

- Edit summaries are optional free text: keyword classes are a lower bound.
- Deleted pages and deleted revisions are invisible, so pages that were deleted never enter.
- Bots removed by user group and account name; semi-automated tools (AWB, Twinkle) count as human edits.
- Usernames are only used to count editors and creators; outputs list creators anonymised.
