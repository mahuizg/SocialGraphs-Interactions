#!/usr/bin/env bash
# Re-runs the whole revised analysis from the data in ../pipeline/data (about 10 minutes on a laptop).
set -e
cd "$(dirname "$0")/src"
python r0_edges_prose.py      # prose-only edge list            -> data/edges_prose.csv
python r1_embeddedness.py     # RQ1                             -> results/rq1_*
python r3_homophily.py        # RQ3                             -> results/rq3_*
python r2_text.py             # RQ2                             -> results/rq2_*
# python r4b_openalex_namematch.py  # needs OPENALEX_API_KEY; or: --from-responses ../data/namematch_responses.json
python r4c_namematch_check.py  # check of the accepted name matches -> results/namematch_check.json
python r4_selection.py        # selection check                 -> results/selection_check.json
python r5_validation.py claude  # second labelling round vs first -> results/validation_ai_vs_ai.json
# python r5_validation.py make  # optional: blind sheets for a human round (then: python r5_validation.py score)
python figures.py             # figures/fig1..3 (.png, .pdf)
python make_summary.py        # CONCLUSIONS.md
