"""R0. Second edge definition: links that appear in running prose only.

The original edges (pipeline/data/processed/edges_clean.csv) use every wikilink in the wikitext,
including infoboxes, navigation boxes, reference lists, publication lists and tables. Those links are
often produced by templates or bots and are not an editor choosing to mention a person. Here we
keep only links in paragraphs: reference-type sections, templates, <ref> tags, tables and bulleted /
numbered list lines are removed before links are extracted. The text analysis already drops the same
material, so this makes the network and the text use the same part of the page.

Output: data/edges_prose.csv (source, target), restricted to pages kept in nodes.csv.
"""
import re
from multiprocessing import Pool

import mwparserfromhell as mwp
import pandas as pd

from common import DATA, PROC, RAW

DROP_SECTIONS = {"references", "notes", "external links", "further reading", "see also", "bibliography",
                 "sources", "citations", "footnotes", "notes and references", "selected publications",
                 "publications", "selected works", "works", "selected bibliography", "references and notes"}
BAD_NS = {"file", "image", "category", "wikipedia", "template", "help", "portal", "wikt"}


def norm(t):
    t = re.sub(r"\s+", " ", t.split("#", 1)[0].replace("_", " ").strip())
    return t[:1].upper() + t[1:] if t else t


def prose_links(qid):
    f = RAW / "wikitext" / f"{qid}.wiki"
    if not f.exists():
        return qid, []
    code = mwp.parse(f.read_text())
    keep = []
    for sec in code.get_sections(levels=[2], include_lead=True, flat=False):
        h = sec.filter_headings()
        if h and h[0].title.strip_code().strip().lower() in DROP_SECTIONS:
            continue
        keep.append(str(sec))
    code = mwp.parse("\n".join(keep))
    for tag in code.filter_tags(recursive=True):
        if str(tag.tag).lower() in ("ref", "table", "gallery", "references"):
            try:
                code.remove(tag)
            except ValueError:
                pass
    for tpl in code.filter_templates(recursive=False):   # infobox, navboxes, citation templates
        try:
            code.remove(tpl)
        except ValueError:
            pass
    text = "\n".join(l for l in str(code).split("\n") if not re.match(r"\s*[*#;:|!{]", l))  # list / table lines
    links = [norm(str(l.title)) for l in mwp.parse(text).filter_wikilinks()]
    return qid, [l for l in links if l and l.split(":")[0].lower() not in BAD_NS]


if __name__ == "__main__":
    people = pd.read_csv(PROC / "scientists_wikidata.csv")
    red = pd.read_csv(PROC / "redirects.csv")
    kept = set(pd.read_csv(PROC / "nodes.csv").qid)
    canon = dict(zip(people.title.map(norm), people.qid))
    for a, b in zip(red.redirect, red.target):
        if norm(str(b)) in canon:
            canon[norm(str(a))] = canon[norm(str(b))]
    with Pool(2) as p:
        res = p.map(prose_links, list(people.qid), chunksize=200)
    edges = sorted({(q, canon[l]) for q, ls in res for l in ls
                    if l in canon and canon[l] != q and q in kept and canon[l] in kept})
    pd.DataFrame(edges, columns=["source", "target"]).to_csv(DATA / "edges_prose.csv", index=False)
    all_e = pd.read_csv(PROC / "edges_clean.csv")
    print(f"prose-only edges: {len(edges)}  (all-wikilink edges: {len(all_e)})")
