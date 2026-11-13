# Who Gets Remembered? — data collection

Three scripts, run in order from inside the `project/` folder. Each one is safe to
re-run: what's already downloaded is cached in `data/raw/` and skipped.

| Step | Script                | Source          | Produces                                                                     |
| ---- | --------------------- | --------------- | ---------------------------------------------------------------------------- |
| 1    | `src/01_wikidata.py`  | Wikidata SPARQL | `data/wikidata_scientists.csv` (who, gender, birth year, ORCID, OpenAlex ID) |
| 2    | `src/02_wikipedia.py` | Wikipedia API   | `data/nodes.csv`, `data/edges.csv`, `data/text/<qid>.txt`                    |
| 3    | `src/03_openalex.py`  | OpenAlex API    | `data/impact.csv`, `data/raw/openalex_name_candidates.jsonl`                 |

Every query is appended to `data/data_log.csv` (date, source, what, how many records).

## The dataset at a glance

|                        |                                                                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Scientists (nodes)     | 9,857 physicists and chemists, born 1920–1980, with an English Wikipedia page                                                          |
| Links (edges)          | 10,645 directed links between scientists in the set (about 1 per scientist, so the graph is sparse)                                    |
| Page length            | median 377 words; some pages are empty                                                                                                 |
| Links per page         | median 34 links to any Wikipedia page                                                                                                  |
| With impact data       | 3,161 have an ORCID or OpenAlex ID on Wikidata: 3,010 matched via ORCID, about 50 via OpenAlex ID, 101 `id_not_found` (no impact data) |
| Impact (those matched) | median 19,500 citations, median h-index 67                                                                                             |

Two consequences shape the analysis (see "Known limitations"):

1. Impact exists for only about a third of the scientists, and those are the
   high-impact ones.
2. The graph is sparse, so many pages have in-degree 0.

## Setup (once)

```powershell
cd project
pip install -r requirements.txt
copy .env.example .env      # then open .env and fill in the two lines
```

- `CONTACT_EMAIL` — Wikimedia asks scripts to identify themselves with a contact.
- `OPENALEX_API_KEY` — free, required since Feb 2026: make an account at openalex.org, copy the key from openalex.org/settings/api.

`.env` is git-ignored, so the key never goes to GitHub.

## Run

```powershell
python src/01_wikidata.py                 # ~1 min. Prints counts by field and gender
python src/02_wikipedia.py --limit 100    # quick test first
python src/02_wikipedia.py                # everyone (~5-10 min per 3,000 pages, so longer for 9,857)
python src/03_openalex.py --limit 50      # quick test first
python src/03_openalex.py                 # everyone
```

**Scope.** The plan targeted 1,500–3,000 nodes, but step 1 returned 9,857. We keep all
of them: the graph is already sparse, and dropping nodes would remove links and
distort the network. Don't subsample nodes at random afterwards, for the same reason.
To narrow the scope anyway, do it _before_ step 2 (one field, or a shorter birth
range), for example
`python src/01_wikidata.py --fields physicist --min-year 1930 --max-year 1975`.
If a group (e.g. women) turns out too small, widen with `--subclasses` (adds e.g.
"theoretical physicist").

## Decisions worth writing in Methods

- **Who counts:** humans with occupation (P106) = physicist / chemist directly (not sub-occupations unless `--subclasses`), born 1920–1980, with an English Wikipedia page.
- **Gender:** Wikidata P21 as recorded; `missing` and `multiple` are kept in the file and reported, not guessed. Wikidata gender is mostly binary, and we say so.
- **Birth year:** if Wikidata lists two different years, `birth_year_conflict` is True. Report how many.
- **Links:** `[[wikilinks]]` written in the page source, including the infobox (e.g. doctoral advisor), but **not** navbox templates, which aren't expanded. Redirects are resolved; self-links are dropped. `n_links` = how many times the link appears.
- **Text:** references, templates/infobox, tables, files and categories removed; everything from the first References / Notes / See also / External links / (Selected) publications heading onward is cut.
- **Impact:** only via IDs that Wikidata provides (OpenAlex ID first, then ORCID). If one person has several OpenAlex profiles, the one with the most works is kept and `n_openalex_profiles` records the split. `name_similarity` flags suspicious ID matches.
- **People with no ID:** the top 5 name-search candidates are saved but **not** used. Picking among them is Phase 2, with a hand-checked sample of 100.
- **Snapshot:** `nodes.csv` stores each page's `revid` and timestamp, so the exact version can be cited.
- **Which impact variable:** `cited_by_count` is the main one; `h_index`, `works_count` and `i10_index` are for robustness. Do not use `first_pub_year`: it is noisy. Use `birth_year` for age.

## Output columns

- `wikidata_scientists.csv`: qid, title, gender, birth_year, fields, orcid, openalex_id, birth_year_conflict
- `nodes.csv`: the columns above plus wiki_title, n_chars, n_words, n_links_total, revid, rev_timestamp
- `edges.csv`: source_qid, target_qid, n_links (directed: source links to target). A person's in-degree is how often they appear as a target.
- `impact.csv`: qid, match_method, n_openalex_profiles, first_pub_year, openalex_id, oa_display_name, oa_orcid, works_count, cited_by_count, h_index, i10_index, top_topic, top_field, last_institution, name_similarity

`qid` is the key that links every file together.

## Known limitations

- **Impact coverage is selective.** Only people with an ORCID or OpenAlex ID on Wikidata have impact data, and that is probably not random (it likely favours living and more recent scientists). Report coverage by gender, birth decade and field before comparing anyone.
- **Sparse graph.** With about one edge per node, many pages have in-degree 0 and PageRank is unstable. In-degree is the main visibility measure and PageRank is secondary. Compute network measures on the full 9,857-node graph, and use the impact subset only in the models, so no edges are lost.
- **What a link means.** Many links are advisor, student or collaborator links, not general "visibility". In-degree partly counts academic relationships inside the set.
- **Everyone here already has a Wikipedia page.** If women need higher impact to get a page, the gap we measure is understated. State this in the Discussion.
- **Citations are not neutral.** They carry their own gender gap, hyperauthorship inflates counts in particle physics, and split OpenAlex profiles (e.g. after a name change) can undercount some people. Report match quality by gender.

## Next steps (Phase 2)

1. Missingness table: gender × has ID × has impact × birth decade × field, with the number of women who have impact (milestone M1: at least 100).
2. In-degree by gender: share with in-degree 0, and the distribution among the rest.
3. Hand-check about 100 ID matches, over-sampling low `name_similarity`, separately for women and men.
4. Try to recover the 101 `id_not_found` rows by looking them up through ORCID.
5. Check the empty pages (zero words): drop them or re-download.
