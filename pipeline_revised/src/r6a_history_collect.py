"""Extra analysis (history): collect the edit history of every scientist page.

This script is an ADD-ON. It does not change any existing data, result or figure. It reads the page list
from ../pipeline/data/processed/nodes.csv (read-only, via common.load_nodes) and writes only to
pipeline_revised/data/history/.

What it collects (English Wikipedia MediaWiki API, metadata only, no page text):
  1. Every revision of every page up to the date the rest of the data were collected (13 Nov 2026):
     timestamp, editor, anonymous flag, page size after the edit, minor flag, edit summary, tags.
     -> data/history/revisions/part_*.jsonl.gz   (one JSON line per page)
  2. The list of accounts in the 'bot' user group, to drop bot edits.
     -> data/history/bots.json
  3. Templates on each page's talk page that record WikiProjects (e.g. Women in Red, Articles for creation)
     and past deletion discussions (Old AfD, Old prod).
     -> data/history/talk_templates.csv
  Every request batch is logged to data/history/collect_log.csv (the existing data logs are not touched).

Resumable: re-running skips pages that are already saved. Stop it at any time with Ctrl+C.
Pages in physics/chemistry (the network in the paper) are collected first, biology last.

Run (from pipeline_revised/src):
    python r6a_history_collect.py                 # everything (~1-2 h)
    python r6a_history_collect.py --limit 50      # quick test on 50 pages
    python r6a_history_collect.py --skip-revisions   # only bots + talk templates
"""
import argparse
import csv
import datetime as dt
import gzip
import json
import os
import re
import time
from pathlib import Path

import requests

from common import DATA, load_nodes

API = "https://en.wikipedia.org/w/api.php"
CUTOFF = "2026-11-13T23:59:59Z"      # same snapshot date as the link and text data
# Wikimedia asks for a contact in the User-Agent: set WGR_CONTACT to your DTU e-mail before running.
UA = ("SGI-WhoGetsRemembered/0.2 (DTU 02805 course project, edit-history add-on; "
      f"{os.environ.get('WGR_CONTACT', 'student project, DTU')}) python-requests")
HIST = DATA / "history"
PARTS = HIST / "revisions"
LOG = HIST / "collect_log.csv"
PART_SIZE = 50                       # pages per saved file
COMMENT_MAX = 300                    # characters of each edit summary kept

TALK_KEEP = re.compile(r"^Template:(WikiProject|Old ?(AfD|XfD|prod|moves?)|Oldafdfull|Afd|Article ?history|"
                       r"Women in Red|DYK|Did you know|Connected contributor|COI|Notability)", re.I)

SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA
_last = {"t": 0.0}


def get(params, interval, retries=6):
    """GET the API with a minimum gap between requests, maxlag and backoff on 429/5xx."""
    params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
    for i in range(retries):
        wait = _last["t"] + interval - time.time()
        if wait > 0:
            time.sleep(wait)
        _last["t"] = time.time()
        try:
            r = SESSION.get(API, params=params, timeout=120)
        except requests.RequestException:
            time.sleep(2 ** i)
            continue
        if r.status_code == 200:
            js = r.json()
            if js.get("error", {}).get("code") == "maxlag":
                time.sleep(float(r.headers.get("Retry-After", 5)))
                continue
            return js
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(float(r.headers.get("Retry-After", 2 ** (i + 1))), 120))
            continue
        r.raise_for_status()
    raise RuntimeError(f"failed after {retries} tries: {params}")


def log(query, n, note=""):
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp_utc", "source", "query", "n_records", "note"])
        w.writerow([dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "Wikipedia API", query, n, note])


def compact(rev):
    """One revision as a short list (keeps the files small)."""
    return [rev.get("timestamp"),
            None if rev.get("userhidden") else rev.get("user"),
            rev.get("userid", 0),
            int(bool(rev.get("anon"))),
            rev.get("size", 0),
            int(bool(rev.get("minor"))),
            None if rev.get("commenthidden") else (rev.get("comment") or "")[:COMMENT_MAX],
            "|".join(rev.get("tags", [])),
            rev.get("revid"),
            rev.get("parentid")]


REV_FIELDS = ["ts", "user", "userid", "anon", "size", "minor", "comment", "tags", "revid", "parentid"]


def page_history(title, interval):
    """All revisions of one page (oldest first) up to CUTOFF. Follows redirects/moves to the current page."""
    params = {"action": "query", "prop": "revisions", "titles": title, "redirects": 1,
              "rvprop": "ids|timestamp|user|userid|size|comment|tags|flags", "rvlimit": "max",
              "rvdir": "newer", "rvend": CUTOFF}
    revs, pageid, resolved, n_req = [], None, title, 0
    while True:
        js = get(params, interval)
        n_req += 1
        pages = js.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing") or pages[0].get("invalid"):
            return None, None, [], n_req
        p = pages[0]
        pageid, resolved = p.get("pageid"), p.get("title", title)
        revs += [compact(r) for r in p.get("revisions", [])]
        if "continue" not in js:
            return pageid, resolved, revs, n_req
        params.update(js["continue"])


def saved_qids():
    done = set()
    for f in sorted(PARTS.glob("part_*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    done.add(json.loads(line)["qid"])
        except (EOFError, OSError, json.JSONDecodeError):
            print(f"  (ignoring unreadable file {f.name})")
    return done


def write_part(rows):
    k = len(list(PARTS.glob("part_*.jsonl.gz"))) + 1
    while (PARTS / f"part_{k:05d}.jsonl.gz").exists():
        k += 1
    tmp = PARTS / f"part_{k:05d}.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, PARTS / f"part_{k:05d}.jsonl.gz")


def collect_revisions(nodes, interval, limit=None):
    done = saved_qids()
    todo = nodes[~nodes.index.isin(done)]
    if limit:
        todo = todo.head(limit)
    print(f"revisions: {len(done)} pages already saved, {len(todo)} to go")
    buf, failed, n_req, t0 = [], [], 0, time.time()
    for i, (qid, row) in enumerate(todo.iterrows(), 1):
        try:
            pageid, resolved, revs, k = page_history(row.title, interval)
            n_req += k
        except Exception as e:                       # keep going; failures are listed at the end
            failed.append((qid, row.title, repr(e)[:200]))
            continue
        if pageid is None:
            failed.append((qid, row.title, "missing"))
            continue
        buf.append({"qid": qid, "title": row.title, "resolved_title": resolved, "pageid": pageid,
                    "fields": REV_FIELDS, "revs": revs})
        if len(buf) >= PART_SIZE:
            write_part(buf)
            log(f"prop=revisions (metadata, rvend={CUTOFF}) for {len(buf)} pages", sum(len(b["revs"]) for b in buf))
            buf = []
        if i % 100 == 0:
            el = time.time() - t0
            print(f"  {i}/{len(todo)} pages, {n_req} requests, {el/60:.1f} min, "
                  f"~{el / i * (len(todo) - i) / 60:.0f} min left")
    if buf:
        write_part(buf)
        log(f"prop=revisions (metadata, rvend={CUTOFF}) for {len(buf)} pages", sum(len(b["revs"]) for b in buf))
    if failed:
        with open(HIST / "failed_pages.csv", "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(failed)
    print(f"revisions done: {len(todo) - len(failed)} saved, {len(failed)} failed")


def collect_bots(interval):
    bots, params = [], {"action": "query", "list": "allusers", "augroup": "bot", "aulimit": "max"}
    while True:
        js = get(params, interval)
        bots += [u["name"] for u in js["query"]["allusers"]]
        if "continue" not in js:
            break
        params.update(js["continue"])
    (HIST / "bots.json").write_text(json.dumps(sorted(bots), indent=0), encoding="utf-8")
    log("list=allusers augroup=bot", len(bots))
    print(f"bots: {len(bots)} accounts")


def collect_talk(interval):
    """Templates on talk pages, 50 pages per request. Uses the resolved titles from the revision files."""
    titles = {}
    for f in sorted(PARTS.glob("part_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                titles["Talk:" + d["resolved_title"]] = d["qid"]
    keys, rows = list(titles), []
    for s in range(0, len(keys), 50):
        chunk = keys[s:s + 50]
        params = {"action": "query", "prop": "templates", "titles": "|".join(chunk), "tlnamespace": 10,
                  "tllimit": "max"}
        found = {t: set() for t in chunk}
        norm = {}
        while True:
            js = get(params, interval)
            q = js.get("query", {})
            for nm in q.get("normalized", []):
                norm[nm["to"]] = nm["from"]
            for p in q.get("pages", []):
                key = norm.get(p["title"], p["title"])
                for t in p.get("templates", []):
                    if TALK_KEEP.match(t["title"]):
                        found.setdefault(key, set()).add(t["title"])
            if "continue" not in js:
                break
            params.update(js["continue"])
        for t, temps in found.items():
            if t in titles:
                rows.append({"qid": titles[t], "talk_title": t, "templates": "|".join(sorted(temps))})
        if (s // 50) % 20 == 0:
            print(f"  talk templates: {s + len(chunk)}/{len(keys)}")
    with open(HIST / "talk_templates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["qid", "talk_title", "templates"])
        w.writeheader()
        w.writerows(rows)
    log("prop=templates on talk pages (WikiProject / Old AfD / Old prod ...)", len(rows))
    print(f"talk templates: {len(rows)} talk pages")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=0.25, help="seconds between requests (default 0.25)")
    ap.add_argument("--limit", type=int, default=None, help="only this many new pages (for a test)")
    ap.add_argument("--skip-revisions", action="store_true")
    ap.add_argument("--skip-talk", action="store_true")
    a = ap.parse_args()
    PARTS.mkdir(parents=True, exist_ok=True)

    n = load_nodes()
    n = n[n.gender.isin(["male", "female"])].copy()
    n["order"] = (n.field_group == "biology").astype(int)          # paper network first, biology last
    n = n.sort_values(["order", "title"])

    if not (HIST / "bots.json").exists():
        collect_bots(a.interval)
    if not a.skip_revisions:
        collect_revisions(n, a.interval, a.limit)
    if not a.skip_talk:
        collect_talk(a.interval)


if __name__ == "__main__":
    main()
