"""Portfolio audit: static checks always, browser checks with --browser.

Static: internal links, anchors and assets resolve; images have alt text; one h1
per page; no skipped heading levels; lang, title, meta description, viewport;
numeric claims on pages that do not appear in any evidence file (listed for a
human to verify, not judged); each project has a README and tests.
Browser (Playwright, local server on 127.0.0.1 only): at 375, 768 and 1280 px
widths, horizontal overflow, console errors, failed requests, screenshots.

Exit 1 on any FAIL. CLAIM and NOTE lines are for review, not failures.
"""
from __future__ import annotations
import argparse, functools, http.server, json, re, threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

WIDTHS = (375, 768, 1280)
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?%|\d+\.\d+)(?![\w])")
EVIDENCE_GLOBS = ("assets/*.json", "assets/*.js", "assets/*.csv", "projects/*/README.md", "projects/*/output*/**/*",
                  "projects/*/docs/**/*", "CONTRIBUTIONS.md", "README.md")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.imgs_no_alt, self.headings = [], set(), 0, []
        self.lang = self.title = self.desc = self.viewport = False
        self.text, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        if tag == "html" and a.get("lang"): self.lang = True
        if tag == "title": self.title = True
        if tag == "meta" and a.get("name") == "description" and a.get("content"): self.desc = True
        if tag == "meta" and a.get("name") == "viewport": self.viewport = True
        if tag in ("a", "link") and a.get("href"): self.links.append(a["href"])
        if tag in ("img", "script", "source") and a.get("src"): self.links.append(a["src"])
        if tag == "img" and a.get("alt") is None: self.imgs_no_alt += 1
        if re.fullmatch(r"h[1-6]", tag): self.headings.append(int(tag[1]))
        if tag in ("script", "style"): self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"): self._skip -= 1

    def handle_data(self, data):
        if not self._skip: self.text.append(data)


def backed(claim: str, ev_nums) -> bool:
    """A page number is backed if an evidence number rounds to it (percent may be a fraction)."""
    raw = claim.replace(",", "")
    pct = raw.endswith("%")
    v = float(raw.rstrip("%"))
    dec = len(raw.rstrip("%").split(".")[1]) if "." in raw else 0
    tol = 0.5 * 10 ** -dec + 1e-9
    return any(abs(e - v) <= tol or (pct and abs(e * 100 - v) <= tol) for e in ev_nums)


def parse(p: Path) -> Page:
    pg = Page(); pg.feed(p.read_text(encoding="utf-8")); return pg


def static(root: Path, out):
    pages = sorted(root.glob("*.html"))
    parsed = {p.name: parse(p) for p in pages}
    evidence = ""
    for g in EVIDENCE_GLOBS:
        for f in root.glob(g):
            if f.is_file() and f.stat().st_size < 3_000_000 and f.suffix.lower() not in (".zip", ".png", ".webp", ".pdf", ".db", ".sqlite"):
                evidence += f.read_text(encoding="utf-8", errors="ignore")
    ev_nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", evidence.replace(",", ""))]
    external = set()
    for name, pg in parsed.items():
        broken = []
        for href in pg.links:
            u = urlparse(href)
            if u.scheme in ("http", "https"):
                external.add(href); continue
            if u.scheme in ("mailto", "tel", "data", "javascript"):
                continue
            target = (root / unquote(u.path)).resolve() if u.path else root / name
            if u.path and not target.exists():
                broken.append(href); continue
            if u.fragment and target.suffix == ".html":
                ids = parsed[target.name].ids if target.name in parsed else parse(target).ids
                if u.fragment not in ids: broken.append(href)
        out("FAIL" if broken else "PASS", f"{name}: internal links and anchors", ", ".join(broken) or f"{len(pg.links)} checked")
        meta_missing = [k for k in ("lang", "title", "desc", "viewport") if not getattr(pg, k)]
        out("FAIL" if meta_missing else "PASS", f"{name}: lang/title/description/viewport", ", ".join(meta_missing) or "present")
        out("FAIL" if pg.imgs_no_alt else "PASS", f"{name}: images have alt", f"{pg.imgs_no_alt} missing")
        jumps = [f"h{a}->h{b}" for a, b in zip(pg.headings, pg.headings[1:]) if b > a + 1]
        h1 = pg.headings.count(1)
        out("FAIL" if h1 != 1 or jumps else "PASS", f"{name}: heading structure", f"{h1} h1; skips: {', '.join(jumps) or 'none'}")
        text = " ".join(pg.text)
        unbacked = sorted({n for n in NUM.findall(text) if not backed(n, ev_nums)})
        if unbacked:
            out("CLAIM", f"{name}: numbers not found in evidence files", ", ".join(unbacked[:15]) + (" ..." if len(unbacked) > 15 else ""))
    out("NOTE", "external links (not fetched; check by hand or with --browser on a networked machine)", str(len(external)))
    for proj in sorted(p for p in (root / "projects").glob("*") if p.is_dir()):
        missing = [x for x in ("README.md", "tests") if not (proj / x).exists()]
        out("FAIL" if missing else "PASS", f"projects/{proj.name}: README and tests", ", ".join(missing) or "present")
    return [p.name for p in pages]


def browser(root: Path, pages, shots: Path, out):
    from playwright.sync_api import sync_playwright
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    shots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for name in pages:
                for w in WIDTHS:
                    ctx = b.new_context(viewport={"width": w, "height": 900})
                    pg = ctx.new_page()
                    errors, failed = [], []
                    pg.on("console", lambda m: errors.append(m.text[:120]) if m.type == "error" else None)
                    pg.on("requestfailed", lambda r: failed.append(r.url.replace(base, "")))
                    pg.on("response", lambda r: failed.append(f"{r.status} {r.url.replace(base, '')}") if r.status >= 400 and r.url.startswith(base) else None)
                    pg.goto(f"{base}/{name}", wait_until="networkidle")
                    overflow = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    pg.screenshot(path=str(shots / f"{name[:-5]}_{w}.png"), full_page=True)
                    bad = overflow > 1 or errors or failed
                    out("FAIL" if bad else "PASS", f"{name} @{w}px: overflow/console/requests",
                        f"overflow {overflow}px; console errors {len(errors)}; failed {failed[:3]}")
                    ctx.close()
            b.close()
    finally:
        srv.shutdown()


def main():
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(here.parents[4]))
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--out", default=None, help="screenshots and report folder (default <root>/output/portfolio-audit)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    dest = Path(a.out) if a.out else root / "output" / "portfolio-audit"
    rows = []
    def out(status, check, detail=""):
        rows.append({"status": status, "check": check, "detail": detail})
        print(f"{status:<6} {check}  {detail}")
    pages = static(root, out)
    if a.browser:
        browser(root, pages, dest, out)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "report.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    fails = sum(r["status"] == "FAIL" for r in rows)
    claims = sum(r["status"] == "CLAIM" for r in rows)
    print(f"\n{len(rows)} checks, {fails} FAIL, {claims} pages with numbers to verify. Report: {dest / 'report.json'}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
