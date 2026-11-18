# Response to the external review

Status key: **Done** (in `pipeline_revised/`, numbers in `CONCLUSIONS.md`), **Partly**, **Needs people**
(cannot be done by code), **Not run** (code written, needs network access we did not have),
**Left alone** (concerns files in `../pipeline/` or `../project/`, which this revision does not edit).

## Redo

| Review point | Status | What was done, and what came out |
|---|---|---|
| RQ1 headline on raw in-degree, negative binomial or hurdle; add out-degree and isolates; "less embedded"; PageRank to supplement | Done | `r1_embeddedness.py`. Negative binomial, Poisson with robust and clustered SEs, and a hurdle model. Out-degree, reciprocal links, zero-in-link pages and isolates are reported beside in-degree. PageRank is one supplement row. The reviewer's rough figure (about 0.60) is confirmed with the dispersion estimated instead of fixed. |
| RQ3 null within community × decade; report it if 22% vs 16% disappears; percentile no longer separate evidence | Done | `r3_homophily.py`. It does not disappear. Expected share under the new null is about 13%, lower than under the old one, over 10 Louvain partitions. The within-community percentile is removed. |
| RQ2 classifier on masked text against a stratified-permutation null; words within birth decade | Done | `r2_text.py`. Classifier with a within field × decade AUC, 200 full re-runs under shuffled gender. Word log-odds combined within field × decade, plus a split-half replication. |
| Human relabelling of 100 matches and 300 sentences, second person for kappa | Needs people | `r5_validation.py make` wrote blind sheets for two labellers into `validation/`; `score` computes kappa and Wilson intervals. Nobody has filled them in yet. |

## Add

| Review point | Status | What was done |
|---|---|---|
| Selection check by name-matching unmatched people | Not run | `r4b_openalex_namematch.py` is written but untested against the live API (api.openalex.org was blocked where the revision ran). In its place, three checks that need no new data are in `r4_selection.py`: match rates, the gap among unmatched pages, and inverse-probability weighting. |
| Subfield in the strata | Done | Second strata definition (subfield × decade × citation tercile) and subfield as a model control. The gap shrinks a little and holds. |
| Prose-only link version | Done | `r0_edges_prose.py`. The gap is larger with prose-only links, so template and list links were hiding part of it, not creating it. |
| Biology as an interaction | Done | One model with field × gender on the three-field network. No evidence the gap differs by field on the count scale. |

## Errors and inconsistencies listed in the review

| Point | Status | Note |
|---|---|---|
| Main results file overwritten by the 500-shuffle robustness run (z −4.31 vs −4.2 in the docs) | Done here | Confirmed: the file in `../pipeline/results/` has `runs: 500`. Revised result files carry the number of shuffles in their name. The old file is left as it is. |
| "Within every community women sit closer to the edge" (172 of 174, really about 18 communities) | Done | Claim and figure panel removed. |
| "9–15% women in every community"; "not stuck in women's areas" untested | Done | Replaced by the measured range over communities with ≥100 pages, and no claim of even spread. |
| Raw and adjusted numbers mixed (33% vs 51% presented as "the biggest part") | Done | Raw table is labelled as raw. The adjusted figure is the hurdle part 1 (percentage points with CI). |
| "No gender bias in the matching" too strong; check done with AI help | Needs people | Wording changed to intervals. The human check is prepared, not done. |
| h-index from the largest profile, citations summed over split profiles | Done | Stated; robustness row restricted to single-profile matches gives the same answer. |
| Fightin' Words check not independent; not within decade; not Monroe et al. itself | Done | Split-half selection and test; within field × decade; described as a beta-binomial adaptation on document frequencies. |
| Edge counts 12,203 / 10,563 / 10,645 | Explained | 12,203 = all three fields; 10,563 = physics + chemistry graph used for RQ1; 10,645 is from the older `project/` download. The revised docs give the first two with their scope. |
| README lists `pageviews.csv` and `backlinks.csv`; docstring says 12 months, code fetches 60 days; `what_we_did.md` points to another repo; Word lock file committed; `project/` duplicates `pipeline/` | Left alone | All in the original folders. Suggested fix for whoever owns them: delete the two rows, correct the docstring, fix the repo name, `git rm "pipeline/docs/~\$at_we_did.docx"`, and add a line to `project/README.md` saying it is superseded. |
| `requirements.txt` lacks statsmodels, spaCy, scattertext, adjustText | Done here | `pipeline_revised/requirements.txt` is complete for the revised code and names the extra packages the original needs. |

## Bigger methodological points

| Point | Status | Note |
|---|---|---|
| Selection into the comparison set | Partly | See above. The at-equal-citations version for unmatched people is the missing piece. |
| The gap is about embeddedness, not only in-links | Done | Central framing now. The control ladder shows the gap moving from 0.60 to 0.81 when the page's own links are added, flagged as a pathway. |
| Effect size depends on the transform | Done | Count scale is the headline. |
| Edges include non-editorial links | Done | Prose-only edges. |
| Subfield not controlled | Done | |
| HC3 and shuffles treat pages as independent | Partly | The shuffle permutes labels on a fixed network, so it does not assume independent outcomes. Model SEs are also given clustered by link community. A full network model (ERGM-type) was not attempted. |
| Biology framed as robustness but behaves differently | Done | It does not behave differently on the count scale. The page-length difference in biology is reported as a finding. |
| Seed rows are not robustness | Done | Removed. The robustness table now varies edge definition, strata, impact measure, profile type, prizes, cohort and living status. |
| RQ3: null not within community; "to men" z is a mirror image; percentile restates RQ1 | Done | |
| RQ2: masking leaks | Partly | The classifier's strongest words are saved as a leak audit, and a stricter mask changes nothing. The spaCy small model is still what produced the masked text. |
| RQ2: cohort confound unchecked | Done | Within field × decade. |
| RQ2: personal-life recall differs by gender | Done | Result dropped. |
| Top citation quintile 4.9% vs 2.8% | Not pursued | Depends on the word list that was dropped. Listed as a lead. |

## One thing the review did not mention

`project/.env.example` in the public repository contains what looks like a real OpenAlex API key rather than a placeholder.
If it is real, regenerate the key and replace the value in the file with a dummy.

## New caveat found during the revision

The classifier separates women's from men's pages very well (AUC about 0.85 within field and decade). Among the words that
do it are British spellings and a recognisable biography style. That is what one would see if many women's pages were
written recently by few editors. Page creator and creation date would test it and are not in the data.
