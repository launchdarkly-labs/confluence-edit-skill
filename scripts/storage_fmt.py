"""Storage-format helpers: pretty-print (for editing), minify (for push), and
identity extraction for the push guards.

Pretty-print only reflows whitespace *between* tags so the agent can navigate
the file by line. CDATA / code / preformatted regions are protected (their
whitespace is significant). minify() is the inverse, so a pulled-then-pushed
unedited page round-trips byte-identically (real Confluence storage is already
">"-adjacent / single-line).
"""
import re

_PROTECT = re.compile(r'(<!\[CDATA\[.*?\]\]>|<ac:plain-text-body>.*?</ac:plain-text-body>|<pre\b.*?</pre>)', re.S)


def _protect(s):
    chunks = []
    def stash(m):
        chunks.append(m.group(1))
        return f"\x00{len(chunks)-1}\x00"
    return _PROTECT.sub(stash, s), chunks

def _restore(s, chunks):
    return re.sub(r"\x00(\d+)\x00", lambda m: chunks[int(m.group(1))], s)


def pretty(storage):
    """One element boundary per line, leaving text/CDATA untouched."""
    s, chunks = _protect(storage)
    s = re.sub(r'>\s*<', '>\n<', s)
    return _restore(s, chunks)


def minify(storage):
    """Inverse of pretty(): collapse whitespace that sits purely between tags."""
    s, chunks = _protect(storage)
    s = re.sub(r'>\s+<', '><', s)
    return _restore(s, chunks)


def local_ids(storage):
    """Element identities Confluence uses to track nodes across edits."""
    return set(re.findall(r'(?:ac:)?local-id="([^"]+)"', storage)) | \
           set(re.findall(r'ac:macro-id="([^"]+)"', storage))


def comment_refs(storage):
    return set(re.findall(r'ac:inline-comment-marker ac:ref="([^"]+)"', storage))


def well_formed(storage):
    """Cheap balance check: every opened tag is closed (ignores void/self-closing)."""
    from html.parser import HTMLParser
    stack = []
    bad = []
    class P(HTMLParser):
        def handle_starttag(self, tag, attrs): stack.append(tag)
        def handle_startendtag(self, tag, attrs): pass
        def handle_endtag(self, tag):
            if stack and stack[-1] == tag:
                stack.pop()
            elif tag in stack:
                while stack and stack.pop() != tag:
                    pass
            else:
                bad.append(tag)
    p = P(convert_charrefs=True)
    try:
        p.feed(storage)
    except Exception as e:
        return False, [f"parse error: {e}"]
    problems = []
    if stack:
        problems.append(f"unclosed: {stack[-5:]}")
    if bad:
        problems.append(f"unexpected close: {bad[:5]}")
    return (not problems), problems
