---
name: confluence-edit
description: View and safely edit existing Confluence (wiki) pages without disturbing inline comments or rich components (status chips, panels, expands, tables, layouts). Use when the user wants to read, update, rephrase, or make targeted edits to a Confluence page. Does NOT create or search for pages yet — you must already have the page ID or URL.
---

# Confluence View & Edit (comment-safe, storage-native)

You read a page as markdown to understand it, then edit the page's **real
Confluence storage format** directly. Editing the real format (not a markdown
translation) is what keeps inline comments, macros, tables, and layouts intact.

The CLI is bundled in this skill's `scripts` directory. Resolve `SKILL_DIR` to
the directory containing this `SKILL.md`. Python 3, no dependencies.

## Authentication

Installation does not read or store credentials. The CLI requires these
environment variables at runtime:

- `CONFLUENCE_URL` — for example, `https://your-company.atlassian.net`
- `CONFLUENCE_USERNAME` — the user's Atlassian account email
- `CONFLUENCE_API_TOKEN` — an Atlassian API token

They must be available to the process running Cursor or Claude Code. If they
were configured after the agent started, tell the user to restart the app or
session.

If any variable is missing, stop and ask the user to configure it outside the
chat. Never ask the user to paste an API token into chat, print the token, or
write credentials into the repository.

## Workflow

```bash
SKILL_DIR="/path/to/directory-containing-this-SKILL.md"

# 1. UNDERSTAND — read the page as markdown (lossy; comprehension only, do NOT edit this)
python3 "$SKILL_DIR/scripts/cli.py" read <PAGE_ID_OR_URL>

# 2. GET AN EDITABLE COPY — fetch the storage XHTML to a local file
python3 "$SKILL_DIR/scripts/cli.py" pull <PAGE_ID_OR_URL>
# writes ~/.confluence-edit/<id>.xml (pretty-printed)

# 3. EDIT ~/.confluence-edit/<id>.xml with the Edit tool — TARGETED edits only

# 4. SAVE
python3 "$SKILL_DIR/scripts/cli.py" push <PAGE_ID_OR_URL> --dry-run
python3 "$SKILL_DIR/scripts/cli.py" push <PAGE_ID_OR_URL>
```

## Editing the storage file — rules

The `.xml` is Confluence storage format (XHTML), pretty-printed one element per
line so you can navigate it. **Find the spot with `Grep`, read a small window
with `Read offset/limit`, and make a narrow `Edit`.** Do not read or rewrite the
whole file.

1. **Targeted edits only.** Change the text/attributes you mean to change and
   leave everything else byte-for-byte. Never select-all-and-replace or
   regenerate the body — that strips the elements' `local-id`s, Confluence can no
   longer track the edit, comments detach, and `push` will reject it.
2. **Never delete or alter `local-id` / `ac:local-id` / `ac:macro-id`
   attributes.** They are how Confluence tracks each element across versions.
   Keep them on elements you edit in place. When you *add* a brand-new element or
   macro (e.g. a new status chip or table row), give it a fresh unique
   `ac:macro-id`/`local-id` — any unique string works; Confluence normalizes it.
3. **To keep an inline comment, keep its
   `<ac:inline-comment-marker ac:ref="…">…</ac:inline-comment-marker>` tags.**
   You may edit text around/inside them; just don't drop the tags. Deleting them
   orphans the comment.
4. **Don't touch `<![CDATA[…]]>` / code-macro bodies** unless that's the edit.
5. Editing is XHTML, so: to tweak a status chip change its
   `<ac:parameter ac:name="title">…</ac:parameter>`; to add a paragraph insert a
   `<p>…</p>` next to a sibling; etc. Match the surrounding structure.

## Push guards (rejections are actionable)

`push` rejects and tells you what's wrong:

- **Not well-formed** → fix the XHTML you edited.
- **Inline comment orphaned** (an `ac:ref` disappeared) → restore its marker tag,
  or if removal is intended,
  `--allow-removed-comment-refs <ref1>,<ref2>`.
- **"Looks like a regeneration"** (most original element ids gone) → you rewrote
  too much; make narrower edits. Only if a full rewrite is truly intended,
  `--allow-rewrite`.
- **Page changed upstream** → re-`pull` and redo your edit (not bypassable).

Prefer fixing over bypassing. Only use `--allow-removed-comment-refs` /
`--allow-rewrite` when the user clearly wants that.
