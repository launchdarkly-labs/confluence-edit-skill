#!/usr/bin/env python3
"""confluence-edit-skill — comment-safe Confluence editing for agents.

  read <id|url>                 print the page as markdown (lossy, comprehension only)
  pull <id|url>                 fetch storage -> ~/.confluence-edit/<id>.xml + sidecar
  push <id|url> [--dry-run]     convert edited storage -> version-locked PUT, with guards
       [--allow-removed-comment-refs r1,r2]   acknowledge removed comment references
       [--allow-rewrite]           acknowledge a non-targeted edit (most elements regenerated)

Workflow: `read` to understand the page; `pull` to get an editable storage file;
edit the .xml with the Edit tool (targeted edits only); `push`.
"""
import argparse, json, os, sys, datetime
import confluence_api as api
import storage_fmt as sf
import view_md

DIR = os.path.expanduser(
    os.environ.get("CONFLUENCE_EDIT_DIR", "~/.confluence-edit"))
REWRITE_FLOOR = 0.5   # require >=50% of original element ids to survive a push


def _paths(pid):
    return os.path.join(DIR, f"{pid}.xml"), os.path.join(DIR, f"{pid}.sidecar.json")


def cmd_read(args):
    pid = api.extract_page_id(args.page)
    v = api.get_view_html(pid)
    print(view_md.to_markdown(v["html"]))


def cmd_pull(args):
    pid = api.extract_page_id(args.page)
    page = api.get_page(pid)
    editable = sf.to_editable(page["storage"])
    os.makedirs(DIR, exist_ok=True)
    xmlp, scp = _paths(pid)
    open(xmlp, "w").write(editable)
    json.dump({
        "page_id": pid, "title": page["title"], "status": page["status"],
        "version": page["version"],
        "orig_storage": page["storage"],
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, open(scp, "w"), indent=1)
    nids = len(sf.local_ids(page["storage"]))
    nrefs = len(sf.comment_refs(page["storage"]))
    print(f"pulled '{page['title']}' v{page['version']} -> {xmlp}")
    print(f"  {len(editable.splitlines())} lines, {nids} element ids, {nrefs} inline comment(s)")
    print("  edit the .xml with targeted edits (keep element tags & local-id/ac:ref intact), then push")


def cmd_push(args):
    pid = api.extract_page_id(args.page)
    xmlp, scp = _paths(pid)
    if not os.path.exists(scp):
        sys.exit(f"no local pull for {pid} (run: pull first)")
    sc = json.load(open(scp))
    orig = sc["orig_storage"]
    editable = open(xmlp).read()
    if editable == sf.to_editable(orig):
        print("no change — nothing to push.")
        return
    edited = sf.to_storage(editable)

    problems = []

    # 1. well-formedness
    ok, why = sf.well_formed(edited)
    if not ok:
        problems.append("storage is not well-formed: " + "; ".join(why))

    # 2. comment preservation
    lost_refs = sf.comment_refs(orig) - sf.comment_refs(edited)
    acked = {
        x.strip()
        for x in (args.allow_removed_comment_refs or "").split(",")
        if x.strip()
    }
    unacked = lost_refs - acked
    if unacked:
        problems.append("inline comments would be orphaned: " + ", ".join(sorted(unacked)))
        problems.append(
            "  -> keep their <ac:inline-comment-marker> tags, or "
            "--allow-removed-comment-refs " + ",".join(sorted(unacked)))

    # 3. anti-clobber: did this stay a *targeted* edit?
    oids, eids = sf.local_ids(orig), sf.local_ids(edited)
    preserved = len(oids & eids)
    if oids and preserved < REWRITE_FLOOR * len(oids) and not args.allow_rewrite:
        problems.append(
            f"looks like a regeneration, not a targeted edit: only {preserved}/{len(oids)} "
            f"original element ids survived. Confluence can't track-edit this and comments/macros "
            f"may detach. Make narrower edits, or --allow-rewrite to override.")

    if problems:
        print("PUSH REJECTED:\n" + "\n".join("  " + p for p in problems))
        sys.exit(2)

    print(f"guards OK | element ids preserved {preserved}/{len(oids)} | "
          f"comments {len(sf.comment_refs(edited))} | changed")
    if args.dry_run:
        print("dry-run — would push.")
        return

    live = api.current_version(pid)
    if live != sc["version"]:
        sys.exit(f"PUSH REJECTED: page changed upstream (pulled v{sc['version']}, now v{live}). Re-pull.")
    new_v = api.put_page(pid, edited, sc["version"], sc["title"], sc["status"],
                         "Edited via confluence-edit-skill")
    print(f"pushed: v{sc['version']} -> v{new_v}")
    sc["version"] = new_v
    sc["orig_storage"] = edited
    json.dump(sc, open(scp, "w"), indent=1)


def main():
    p = argparse.ArgumentParser(prog="confluence-edit-skill")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read"); r.add_argument("page"); r.set_defaults(fn=cmd_read)
    pl = sub.add_parser("pull"); pl.add_argument("page"); pl.set_defaults(fn=cmd_pull)
    ps = sub.add_parser("push"); ps.add_argument("page")
    ps.add_argument("--dry-run", action="store_true")
    ps.add_argument("--allow-removed-comment-refs", default="")
    ps.add_argument("--allow-rewrite", action="store_true")
    ps.set_defaults(fn=cmd_push)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
