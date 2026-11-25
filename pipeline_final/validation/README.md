# Validation of the hand labels

Two checks in the analysis rest on hand labels:

- **100 OpenAlex matches** (`../../data_collection/data/processed/handcheck_sample.csv`): is the OpenAlex profile the same person as
  the Wikipedia page (`correct`), and does it look like the whole career (`profile_complete`)?
- **300 sentences** (`../../data_collection/results/sentences_to_label.csv`): `is_personal` (family, marriage, children, private life)
  and `is_professional` (research, jobs, degrees, prizes). Both or neither is allowed.

## Status (18 Nov 2026): two rounds done, both AI-assisted

| Round | Who | Files |
|---|---|---|
| 1 | AI-assisted (original pipeline) | the two files above |
| 2 | Claude, 18 Nov 2026 | `matches_labeller.csv`, `sentences_labeller.csv` (this folder) |

Scored with `cd ../src && python r5_validation.py claude` → `../results/validation_ai_vs_ai.json`. Results are written into
`../CONCLUSIONS.md` (section *Validation of the labels*).

| Label | Agreement round 1 vs 2 | Cohen's kappa |
|---|---|---|
| Match correct | 100% (100/100 correct in both) | not defined (no negatives) |
| Profile complete | 98% | 0.66 |
| Sentence personal | 99.7% | 0.99 |
| Sentence professional | 99.0% | 0.98 |

Match accuracy by gender: 50 of 50 women and 50 of 50 men, 95% Wilson interval 93% to 100% each.
The script also re-estimates the personal word list with the round-2 labels: recall 46% on women's pages vs
33% on men's (difference 95% interval -0.18 to +0.46), so the list stays dropped.

**How round 2 was done, and its limits**

- Matches were checked from data, not by opening both pages: correct when the OpenAlex name or an alias contains the Wikipedia
  surname and words from the profile's main OpenAlex topics appear in the Wikipedia page. `profile_complete` uses a crude rule
  (at least one work per career year since age 25). The `comment` column records the evidence for each row.
- Sentences were read and labelled one by one, but the round-1 labels had been seen first, so this is not blind.

This shows the labels are stable across two AI rounds. **It is not human validation.** The paper says
"both labelling rounds were done with AI assistance".

## Optional: a human round

If a group member wants to turn this into human validation:

```bash
cd ../src && python r5_validation.py make    # writes blind matches_labeller_A/B.csv and sentences_labeller_A/B.csv
# each person fills in their own pair (1 or 0), without looking at the other's or at the AI labels; about an hour each
python r5_validation.py score                # -> ../results/validation_human.json (kappa A-B, A-vs-AI, Wilson intervals)
```

Then update the validation sentence in `../paper/main.tex` (Discussion and Materials and Methods).
