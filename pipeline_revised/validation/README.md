# Human validation (to do)

The first round of checks was labelled with AI help, which is a model checking a model.
Two people each fill in their own pair of sheets, without looking at the other's or at the AI labels:

| File | Rows | Fill in (1 or 0) |
|---|---|---|
| `matches_labeller_A.csv`, `matches_labeller_B.csv` | 100 | `correct`: is the OpenAlex profile the same person as the Wikipedia page? `profile_complete`: does the profile look like the whole career? |
| `sentences_labeller_A.csv`, `sentences_labeller_B.csv` | 300 | `is_personal`: family, marriage, children, private life. `is_professional`: research, jobs, degrees, prizes. Both or neither is allowed. |

Open both links in each matches row. Gender and the sampling strata are hidden on purpose.
About an hour per person. Then:

```bash
cd ../src && python r5_validation.py score     # -> results/validation_human.json
```

It reports Cohen's kappa between the two people, kappa between a person and the AI labels, and match accuracy by gender
with Wilson intervals. Report the intervals in the paper. With 50 matches per gender, "no difference" is not a claim the
sample can support; "50 of 50 correct, 95% interval 93% to 100%" is.
