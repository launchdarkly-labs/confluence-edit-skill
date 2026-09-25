"""Lossy HTML(view) -> markdown for COMPREHENSION only. Never used for writing,
so fidelity doesn't matter — it just has to be readable and cheap. Unknown
elements are rendered transparently (their children), so it degrades gracefully.
"""
from html.parser import HTMLParser

BLOCK = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6",
         "ul", "ol", "li", "table", "tr", "blockquote", "pre"}


class _Node:
    __slots__ = ("tag", "attrs", "kids", "text")
    def __init__(self, tag, attrs=None, text=None):
        self.tag, self.attrs, self.kids, self.text = tag, dict(attrs or {}), [], text


class _Build(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root"); self.stack = [self.root]
    def handle_starttag(self, tag, attrs):
        n = _Node(tag, attrs); self.stack[-1].kids.append(n); self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(_Node(tag, attrs))
    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]; break
    def handle_data(self, data):
        self.stack[-1].kids.append(_Node("#text", text=data))


def _inline(n):
    if n.tag == "#text":
        return n.text or ""
    if n.tag in ("strong", "b"):
        return "**" + "".join(_inline(k) for k in n.kids).strip() + "**"
    if n.tag in ("em", "i"):
        return "*" + "".join(_inline(k) for k in n.kids).strip() + "*"
    if n.tag == "code":
        return "`" + "".join(_inline(k) for k in n.kids) + "`"
    if n.tag == "a":
        return "[" + "".join(_inline(k) for k in n.kids).strip() + "](" + n.attrs.get("href", "") + ")"
    if n.tag == "br":
        return " "
    if n.tag == "img":
        return "![" + n.attrs.get("alt", "image") + "](" + n.attrs.get("src", "") + ")"
    return "".join(_inline(k) for k in n.kids)


def _cell(n):
    return " ".join("".join(_inline(k) for k in n.kids).split()).replace("|", r"\|")


def _block(n, out, depth=0):
    t = n.tag
    if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
        out.append("#" * int(t[1]) + " " + _inline(n).strip())
    elif t == "p":
        s = _inline(n).strip()
        if s:
            out.append(s)
    elif t in ("ul", "ol"):
        i = 0
        for li in n.kids:
            if li.tag == "li":
                i += 1
                marker = "  " * depth + ("- " if t == "ul" else f"{i}. ")
                # inline part of the li, then any nested lists
                inline = " ".join(_inline(k) for k in li.kids if k.tag not in ("ul", "ol")).strip()
                out.append(marker + inline)
                for k in li.kids:
                    if k.tag in ("ul", "ol"):
                        _block(k, out, depth + 1)
    elif t == "table":
        rows = [r for r in _walk(n, "tr")]
        md = []
        for ri, r in enumerate(rows):
            cells = [_cell(c) for c in r.kids if c.tag in ("td", "th")]
            if not cells:
                continue
            md.append("| " + " | ".join(cells) + " |")
            if ri == 0:
                md.append("| " + " | ".join(["---"] * len(cells)) + " |")
        if md:
            out.append("\n".join(md))
    elif t == "blockquote":
        inner = []
        for k in n.kids:
            _block(k, inner, depth)
        out.append("\n".join("> " + l for l in "\n\n".join(inner).split("\n")))
    elif t == "pre":
        out.append("```\n" + _inline(n) + "\n```")
    elif t == "hr":
        out.append("---")
    else:
        # transparent container: recurse into children
        for k in n.kids:
            if k.tag in BLOCK or k.tag in ("table", "hr"):
                _block(k, out, depth)
            elif k.tag == "#text" and (k.text or "").strip():
                out.append(k.text.strip())
            elif k.tag not in ("#text",):
                inl = _inline(k).strip()
                if inl:
                    out.append(inl)


def _walk(n, tag):
    for k in n.kids:
        if k.tag == tag:
            yield k
        yield from _walk(k, tag)


def to_markdown(html):
    b = _Build(); b.feed(html)
    out = []
    _block(b.root, out)
    # collapse blank runs
    text = "\n\n".join(s for s in out if s.strip())
    return text.strip() + "\n"
