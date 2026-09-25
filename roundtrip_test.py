#!/usr/bin/env python3
"""Round-trip health check over real pages. READ-ONLY — never writes.

  python3 roundtrip_test.py <id|url> [<id|url> ...]

For each page/blogpost: fetch storage and assert the pull/push transform is
lossless (minify(pretty(storage)) == minify(storage)), element ids and comment
refs survive pretty-printing, the storage is well-formed, and Confluence's view
renders to non-empty comprehension markdown. Exits non-zero on any failure.
Page ids come from argv so none are committed to the repo.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import confluence_api as api, storage_fmt as sf, view_md

ID_RE = re.compile(r'(\d{6,})')


def fetch_storage(cid):
    for kind in ("pages", "blogposts"):
        try:
            _, d = api._req("GET", api.api_url(
                f"/wiki/api/v2/{kind}/{cid}?body-format=storage"))
            return kind, d["title"], d["body"]["storage"]["value"]
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                continue
            raise
    raise RuntimeError(f"{cid}: not found")


def check(ref):
    m = ID_RE.search(ref)
    if not m:
        raise ValueError(f"no id in {ref!r}")
    cid = m.group(1)
    kind, title, s = fetch_storage(cid)
    p = sf.pretty(s)
    lossless = sf.minify(p) == sf.minify(s)
    ids_ok = sf.local_ids(p) == sf.local_ids(s)
    refs_ok = sf.comment_refs(p) == sf.comment_refs(s)
    wf, why = sf.well_formed(s)
    md = view_md.to_markdown(api.get_view_html(cid)["html"])
    lines = p.splitlines()
    longest = max((len(l) for l in lines), default=0)
    ok = lossless and ids_ok and refs_ok and wf and len(md.strip()) > 0

    print(f"\n[{'PASS' if ok else 'FAIL'}] {kind[:-1]} {cid} — {title}")
    print(f"   storage {len(s):,}c | pretty {len(lines)} lines, longest {longest}c "
          f"| comprehension md ~{len(md)//4} tok")
    print(f"   pretty/minify lossless: {lossless} | ids preserved: {ids_ok} | "
          f"refs preserved: {refs_ok} | well-formed: {wf} {why if why else ''}")
    return ok


def main():
    refs = sys.argv[1:]
    if not refs:
        sys.exit("usage: roundtrip_test.py <id|url> [<id|url> ...]")
    results = [check(r) for r in refs]
    print(f"\n{sum(results)}/{len(results)} pages passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
