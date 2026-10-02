"""Storage-format helpers for editable layout and push validation.

The editable representation adds line breaks only between directly adjacent
tags. Existing whitespace is left untouched. CDATA, code, and preformatted
regions are protected because their contents may include tag-like text.
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


def to_editable(storage):
    """Add navigational line breaks without changing existing whitespace."""
    s, chunks = _protect(storage)
    s = s.replace('><', '>\n<')
    return _restore(s, chunks)


def to_storage(editable):
    """Collapse bare tag-boundary line breaks before sending storage."""
    s, chunks = _protect(editable)
    s = s.replace('>\n<', '><')
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
