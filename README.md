# confluence-edit-skill

A lightweight tool to safely make small edits to large Confluence pages.

This skill is battle-tested and used internally. Bugfixes welcome, but there's no specific roadmap for evolving this tool.

## The problem

Atlassian's official MCP loads the entire page's content into an agent's context when making an edit. This can be expensive when working with a large page.

Other Confluence skills solve this by converting the page's content to Markdown, reducing the size significantly. However, this is a lossy conversion:

- **flattens rich content** — status chips, panels, expands, dates, @mentions,
  and layouts turn into plain text, or vanish;
- **kills in-line comments** — Confluence comments are anchored to spans in the
  document, which are lost in the Markdown conversion;
- **rewrites the whole page** — the version diff shows everything as changed, so
  no one can tell what the edit actually did.

## The approach

`confluence-edit-skill` avoids the context blow-up with a **pull / push** workflow:

- `pull` writes the page's storage to a file on disk. The agent finds and edits
  just the relevant spans (grep + small reads), so it never loads the whole page
  into context.
- `push` saves that file back, blocking changes that unintentionally rewrite content.

And `read` renders a page as Markdown when an agent just wants to read it
end-to-end.

### Safety

`push` refuses any change that is probably too destructive, explains why, and
offers an explicit override when you truly mean it:

- **Orphaned comments.** If an edit drops an inline comment's anchor, push stops.
  Keep the comment's marker tag to preserve it, or pass
  `--allow-removed-comment-refs <ref>` to acknowledge its removal.
- **Full rewrites.** If an edit regenerates most of the page instead of changing a
  targeted span — measured by how many of the page's original element IDs survive
  — push stops. This is the failure mode where an agent hand-writes a whole "new
  version" and silently detaches every comment and macro. Pass `--allow-rewrite`
  only for a deliberate full rewrite.
- **Concurrent edits (version races).** `push` writes the change as version *N+1*
  of the version you pulled. It pre-checks the live version and stops if the page
  moved since your pull; and as a backstop, Confluence itself rejects any write
  whose version number isn't exactly the next one (HTTP 409). So a concurrent
  edit can never be silently clobbered — re-pull and reapply.

## Installation

The skill runtime requires Python 3 and no third-party packages.

Install it globally for Cursor and Claude Code with the
[Agent Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add launchdarkly-labs/confluence-edit-skill \
  --skill confluence-edit --global \
  --agent cursor --agent claude-code
```

Alternatively, clone the repository and copy the self-contained root skill to
either agent's global skill directory:

```bash
git clone --depth 1 https://github.com/launchdarkly-labs/confluence-edit-skill.git
for target in ~/.cursor/skills/confluence-edit ~/.claude/skills/confluence-edit; do
  mkdir -p "$target"
  cp confluence-edit-skill/SKILL.md "$target/"
  cp -R confluence-edit-skill/scripts "$target/"
done
```

You can also ask Cursor or Claude to install `confluence-edit` globally from
this repository URL.

Installation does not configure authentication. Expose these variables to the
Cursor or Claude Code process using your normal shell or secret-management
setup:

```bash
export CONFLUENCE_URL="https://your-company.atlassian.net"
export CONFLUENCE_USERNAME="you@company.com"
export CONFLUENCE_API_TOKEN="…"
```

Create the API token under id.atlassian.com → Security → API tokens. If the
agent was already running when you configured the variables, restart the app or
session. Never commit the token to the repository.

The account needs permission to view the page and its space. Pushing also
requires permission to update pages in the space.

**This is not a full Confluence integration.** The `confluence-edit` skill only
*reads and edits existing pages*. For searching, creating pages, comments, or
labels, keep using the Atlassian MCP.

## CLI Usage

- **`read <page-id-or-url>`** — print the page as Markdown to read and plan an
  edit. Don't edit this output.
- **`pull <page-id-or-url>`** — download the page's storage to
  `~/.confluence-edit/<id>.xml`. Edit *that file*, keeping element tags,
  `local-id`s, and inline-comment markers intact.
- **`push <page-id-or-url>`** — validate the edited file and save it back as a new
  version. `--dry-run` runs the guards without writing.
