"""Minimal Confluence Cloud API layer (v2 storage GET/PUT).

Configuration, in priority order:
  1. env vars CONFLUENCE_URL + CONFLUENCE_USERNAME + CONFLUENCE_API_TOKEN
  2. the mcp-atlassian server config in ~/.claude.json

Credentials are read at runtime; they are never written into this repo.
"""
import base64, json, os, re, urllib.request, urllib.error
from functools import lru_cache

CLAUDE_CONFIG = os.path.expanduser(
    os.environ.get("CLAUDE_CONFIG_PATH", "~/.claude.json"))


def _creds_from_mcp():
    try:
        d = json.load(open(CLAUDE_CONFIG))
        env = d.get("mcpServers", {}).get("mcp-atlassian", {}).get("env", {})
        return (env.get("CONFLUENCE_USERNAME"), env.get("CONFLUENCE_API_TOKEN"),
                env.get("CONFLUENCE_URL"))
    except Exception:
        return (None, None, None)


def _resolve_auth():
    """Return a Basic auth header and the configured Confluence domain."""
    user = os.environ.get("CONFLUENCE_USERNAME")
    token = os.environ.get("CONFLUENCE_API_TOKEN")
    url = os.environ.get("CONFLUENCE_URL")
    if not (user and token):
        muser, mtoken, murl = _creds_from_mcp()
        user, token, url = user or muser, token or mtoken, url or murl

    missing = [
        name for name, value in (
            ("CONFLUENCE_URL", url),
            ("CONFLUENCE_USERNAME", user),
            ("CONFLUENCE_API_TOKEN", token),
        ) if not value
    ]
    if missing:
        raise RuntimeError(
            "missing Confluence configuration: " + ", ".join(missing) +
            " (set environment variables or configure mcp-atlassian)")

    domain = re.sub(r"^https?://", "", url).split("/")[0]
    basic = base64.b64encode(f"{user}:{token}".encode()).decode()
    return f"Basic {basic}", domain


@lru_cache(maxsize=1)
def _auth_config():
    return _resolve_auth()


def domain():
    return _auth_config()[1]


def api_url(path):
    return f"https://{domain()}{path}"


def auth_kind():
    _auth_config()
    return "api-token"


def extract_page_id(s):
    s = s.strip()
    if s.isdigit():
        return s
    m = re.search(r'/pages/(\d+)', s)
    if m:
        return m.group(1)
    raise ValueError(f"could not parse page id from {s!r}")


def _req(method, url, body=None):
    auth, _ = _auth_config()
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", auth)
    r.add_header("Accept", "application/json")
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:400]}") from None


def get_page(page_id):
    s, d = _req("GET", api_url(
        f"/wiki/api/v2/pages/{page_id}?body-format=storage"))
    return {
        "id": d["id"], "title": d["title"], "status": d.get("status", "current"),
        "version": d["version"]["number"], "storage": d["body"]["storage"]["value"],
    }


def get_view_html(page_id):
    """Confluence's own rendered HTML (for lossy comprehension markdown)."""
    s, d = _req("GET", api_url(
        f"/wiki/rest/api/content/{page_id}?expand=body.view"))
    return {"title": d.get("title", ""), "html": d["body"]["view"]["value"]}


def current_version(page_id):
    s, d = _req("GET", api_url(f"/wiki/api/v2/pages/{page_id}"))
    return d["version"]["number"]


def put_page(page_id, storage, version, title, status, message):
    body = {
        "id": page_id, "status": status, "title": title,
        "body": {"representation": "storage", "value": storage},
        "version": {"number": version + 1, "message": message},
    }
    s, d = _req("PUT", api_url(f"/wiki/api/v2/pages/{page_id}"), body)
    return d["version"]["number"]
