# confluence-edit-skill

Edit Confluence pages with an AI agent, without losing comments or rich content.

## The problem

Most of the time when an agent edits a Confluence page, the page
is converted to Markdown, edited, and written back whole. That:

- **flattens rich content** — status chips, panels, expands, dates, @mentions,
  and layouts turn into plain text, or vanish;
- **kills in-line comments** — Confluence comments are anchored to spans in the
  document, which are lost in the Markdown conversion;
- **rewrites the whole page** — the version diff shows everything as changed, so
  no one can tell what the edit actually did.

Some skills let you opt into the **storage format** (Confluence's native XHTML)
instead, which fixes all of that — but storage is far bulkier than Markdown, and
tools like the Atlassian MCP read the entire body into the agent's context, which
is more expensive (a real page is easily tens of thousands of tokens).

The same status row, both ways:

```
Markdown:  **Status:** In Progress
```
```html
Storage:   <p><strong>Status:</strong> <ac:structured-macro ac:name="status">
             <ac:parameter ac:name="colour">Yellow</ac:parameter>
             <ac:parameter ac:name="title">In Progress</ac:parameter>
           </ac:structured-macro></p>
```

Markdown is compact but loses the chip; storage keeps it but is many times larger.

## The approach

`confluence-edit-skill` makes the storage format the only way to edit, so an agent can't
accidentally mess up unrelated parts of the doc, but avoids the context blow-up with a **pull / push** workflow:

- `pull` writes the page's storage to a file on disk. The agent finds and edits
  just the relevant spans (grep + small reads), so it never loads the whole page
  into context.
- `push` saves that file back, blocking unsafe changes (see Safety).

And `read` renders a page as Markdown when an agent just wants to read it
end-to-end.

## Installation

Requires Python 3 (no dependencies).

```bash
git clone git@github.com:launchdarkly-labs/confluence-edit-skill.git
cd confluence-edit-skill
# Make the confluence-edit skill available to Claude in every project:
ln -s "$PWD/.claude/skills/confluence-edit" ~/.claude/skills/confluence-edit
```

Authenticate with an Atlassian API token (id.atlassian.com → Security → API tokens):

```bash
export CONFLUENCE_URL="https://your-company.atlassian.net"
export CONFLUENCE_USERNAME="you@company.com"
export CONFLUENCE_API_TOKEN="…"
```

If you already use the Atlassian MCP (`mcp-atlassian`), the CLI reuses its token
from `~/.claude.json` automatically — no env vars needed.

**This is not a full Confluence integration.** The `confluence-edit` skill only
*reads and edits existing pages*. For searching, creating pages, comments, or
labels, keep using the Atlassian MCP.

## CLI Usage

- **`read <page-id-or-url>`** — print the page as Markdown to read and plan an
  edit. Don't edit this output.
- **`pull <page-id-or-url>`** — download the page's storage to
  `.confluence/<id>.xml`. Edit *that file*, keeping element tags, `local-id`s,
  and inline-comment markers intact.
- **`push <page-id-or-url>`** — validate the edited file and save it back as a new
  version. `--dry-run` runs the guards without writing.

## Safety

`push` refuses any change Confluence couldn't track cleanly, explains why, and
offers an explicit override when you truly mean it:

- **Orphaned comments.** If an edit drops an inline comment's anchor, push stops.
  Keep the comment's marker tag to preserve it, or pass `--delete-comments <ref>`
  to confirm you meant to delete that commented text.
- **Clobbering.** If an edit regenerates most of the page instead of changing a
  targeted span — measured by how many of the page's original element IDs survive
  — push stops. This is the failure mode where an agent hand-writes a whole "new
  version" and silently detaches every comment and macro. Pass `--allow-rewrite`
  only for a deliberate full rewrite.
- **Concurrent edits (version races).** `push` writes the change as version *N+1*
  of the version you pulled. It pre-checks the live version and stops if the page
  moved since your pull; and as a backstop, Confluence itself rejects any write
  whose version number isn't exactly the next one (HTTP 409). So a concurrent
  edit can never be silently clobbered — re-pull and reapply.
- **Malformed storage.** Push checks that the edited XHTML is well-formed before
  sending it.
