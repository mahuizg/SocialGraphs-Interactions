# What we did: project log
*"Who Gets Remembered?" · DTU 02805 · work session of 13 November 2026*

This file explains, in plain words, everything that was done in this session, why, what went wrong, and what we found.

---

## 1. The goal

We want to know if **women scientists are less visible on Wikipedia than men with the same scientific impact**. Visibility is measured in two ways:

- **Network:** how many other scientists' pages link to theirs, and how central they are (PageRank).
- **Text:** how their pages describe them.

"Same impact" means the same number of citations, the same field, and the same birth decade.

---

## 2. Getting the data

| Step | What we did | Result |
|---|---|---|
| **Who is in the study** | Asked Wikidata for all physicists, chemists and biologists born 1920–1980 that have an English Wikipedia page | 12,773 people, 2,279 women |
| **Wikipedia pages** | Downloaded the text of every page. Most physics and chemistry pages came from our teammate's earlier download, and we fetched only the missing ones | 12,761 pages |
| **The network** | Turned the links between pages into a network: if A's page links to B's page, that is an arrow A → B | 12,203 links |
| **Scientific impact** | Got citations, number of papers and h-index from OpenAlex. We only matched people through their ORCID or OpenAlex ID, never by name, to avoid mixing up people with the same name | 4,146 people matched |
| **Extra information** | Got awards, Nobel prizes, and whether the person has died, from Wikidata | 270 Nobel laureates |

**Final group used for the comparisons:** 2,926 physicists and chemists (606 women, 2,320 men).

### Problems along the way
- **Downloads were slow.** Fetching 50 pages at once took 45 seconds per batch, so we switched to fetching pages one by one in parallel. Then our teammate shared her pages, which saved hours.
- **OpenAlex limits free use.** Searching by name would have taken about 7 days. We decided to use only ID matches, which was already enough.
- **Wikipedia blocked us** for making too many requests. Because of that we **dropped pageviews** (how many people read each page). The group agreed it was not essential; it goes in the paper as a limitation.

---

## 3. Changes after our teammate's review

A teammate sent six comments on the plan. We applied most of them:

- **Fairer comparisons:** compare people within the same field, birth decade and citation level, not by citations alone.
- **Regression with confidence intervals** as a second way to measure the gap.
- **Prizes:** run everything again **without Nobel laureates**, and without the top 1% most-cited people.
- **Other impact measures:** h-index and number of papers, not only citations.
- **Better text method:** "Fightin' Words" to find typical words, plus hiding names, pronouns and gender words so they don't give away who is a woman.
- **Simpler RQ3:** reduced to one clear number.
- **Not done:** checking who *doesn't* have a Wikipedia page at all (point 1). It needs gender to be coded by hand for hundreds of people. Optional if there is time.

---

## 4. Null models (the "is it just chance?" tests)

1. **Main question:** we shuffle the "woman/man" labels at random among people of the same field, decade and citation level, 1,000 times. If the real gap is much bigger than the shuffled ones, it is not chance.
2. **Who links to whom:** we keep the network fixed and shuffle gender within field and decade.
3. **Communities:** we compare with a random network where every page keeps its number of links.

---

## 5. What we found

### RQ1: Are women less central? **Yes.**
- At equal citations, field and decade, women's pages have **about 14% lower PageRank** than men's. This is very unlikely to be chance (z = −4.2).
- The biggest part: **only 33% of women's pages get any link from another scientist's page, against 51% of men's.**
- Even among pages that do get links, women's are about 11% less central.
- Page length is the **same** for women and men.

### RQ3: Structure
- Women's pages get **more links from other women** than chance would give: 22% vs 16% expected.
- Women are spread across all subfields, at about 9–15% of every community. They are not stuck in "women's areas".
- **Inside every community, women sit closer to the edge.** On average they rank at the 40th percentile of centrality, men at the 52nd. This held in at least 98% of the community checks across 10 runs.

### RQ2: Are the pages written differently? **Yes, in some ways.**
- **15.5% of women's pages mention that they are women** ("first woman to…", "female physicist"), against 0.1% of men's.
- Women's pages talk more about **career path**: *education, career, completed, earned, postdoctoral*.
- Men's pages talk more about **the work itself**: *theory, papers, books, known*.
- This pattern holds in physics and in chemistry separately (98% of the top words lean the same way).
- **Personal life** (marriage, children): only a tiny difference, and the word list we used to find it misses most personal sentences. **It is not a reliable result.**

### Robustness: does it hold?
| Version | PageRank, women vs. men |
|---|---|
| Main analysis | 0.85 |
| Without Nobel laureates | 0.87 |
| Without the top 1% | 0.86 |
| Using h-index / number of papers | 0.84 / 0.81 |
| Biology | 0.95: smaller gap, borderline |

The result holds everywhere except biology, where the gap almost disappears and women's pages are even 22% longer. That is worth discussing in the paper.

---

## 6. Quality checks done by hand
- **100 matches checked** (Wikipedia person = OpenAlex person): **100/100 correct**. Profiles complete for 98% of women and 94% of men, so there is no gender bias in the matching. *(Done with AI help; say this in Methods and spot-check a few.)*
- **300 sentences labelled** as personal and/or professional, to test the word lists:
  - Professional list: very good (precision 0.98).
  - Personal list: precise (0.92) but it misses about 2 of every 3 personal sentences (recall 0.36).

---

## 7. The three figures

1. **Figure 1:** citations (x) against PageRank (y), with women in orange and men in blue. The women's line sits below the men's. Next to it, a panel compares the real gap with the gaps you get from random shuffles.
2. **Figure 2:** Scattertext-style word map. Words in the top-left corner are typical of women's pages, words in the bottom-right corner of men's pages. Next to it, personal-life sentences by citation level. There is also an interactive version: `results/fig2_scattertext.html`.
3. **Figure 3:** the nine biggest communities in the network, coloured by gender, with a side panel showing that women sit closer to the edge in every one.

---

## 8. Where everything is

| What | Where |
|---|---|
| Everything in one notebook | `who_gets_remembered.ipynb` (runs in ~5 min using saved data) |
| Scripts, step by step | `src/01_…` to `src/08_…` |
| Figures | `figures/` |
| Results and tables | `results/` (`robustness.md` = robustness table) |
| Every query we made, with dates | `data/data_log.csv` |
| Phase 0 decisions | `docs/scope_note.md` |
| On GitHub | `carlotamontes/socialgraphs-project`, folder `pipeline/` (everything except the notebook) |

---

## 9. Limitations to mention in the paper
- Only people with an ORCID could be matched, and those are younger and more often women, so the results describe that group, not all scientists.
- Citations themselves have a gender gap. We measure the Wikipedia gap **on top of** that.
- Wikidata gender is almost always binary.
- No pageviews (Wikipedia blocked us).
- Communities change a bit between runs, so report patterns, not exact counts.
- The personal-life word list is weak.

## 10. What is left
- Write the paper (≤ 6 pages), the 3 slides and the reflection on AI.
- Optional: the "who doesn't have a page at all" check.
