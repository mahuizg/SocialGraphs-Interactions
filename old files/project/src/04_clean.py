"""Step 4 - Cleaning: build the analysis tables in data/clean/.

Run from inside the project/ folder:
    python src/04_clean.py

First run: also creates two files for you to fill in by hand (never overwritten):
    data/manual/hand_check_matches.csv   -> 'verdict' column: ok / wrong / unsure
    data/manual/birth_year_fixes.csv     -> 'birth_year_fixed' column
After filling them in, run the script again: the verdicts and fixes are applied.

Outputs:
    data/clean/nodes_clean.csv    one row per scientist (the table everyone uses)
    data/clean/edges_clean.csv    links between kept scientists
    data/clean/dropped_nodes.csv  the few pages removed, with the reason
    data/clean/cleaning_log.md    counts after every step, for Methods

All the logic lives in src/cleaning.py; notebooks/04_cleaning.ipynb walks through it.
"""
from cleaning import run_all
from common import log_query


def main():
    res = run_all(write=True)
    print("\nSteps:")
    for step, n, note in res["log"]:
        print(f"  {step:<32} {n:>6,}   {note}")
    log_query("derived", "data/clean/ (nodes_clean, edges_clean) from raw snapshot",
              len(res["nodes"]), f"{len(res['edges'])} edges")


if __name__ == "__main__":
    main()
