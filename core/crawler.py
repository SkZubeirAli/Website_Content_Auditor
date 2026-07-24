"""Breadth-first, same-domain website crawler.

Fetches internal HTML pages only, ignoring assets (images, CSS, JS, fonts,
PDFs, archives, media), external links, mailto/tel links, and duplicate
URLs. Fetching within each BFS "layer" is parallelized with a thread pool
so large sites scan faster, while the crawl as a whole still respects a
stop event so the GUI's Stop button works immediately.
"""
import threading
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin, urldefrag

import requests
from bs4 import BeautifulSoup

IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".css", ".js", ".mjs",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".wav", ".ogg",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".xml", ".json",
}

IGNORED_SCHEMES = {"mailto", "tel", "javascript", "data"}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "ContentAuditorBot/1.0 (+desktop content audit tool)"
    )
}


@dataclass
class CrawledPage:
    url: str
    status_code: int
    title: str
    html: str


def normalize_url(url: str) -> str:
    """Strip the fragment and any trailing slash (except root) so that
    http://site.com/about and http://site.com/about/#team are treated
    as the same page."""
    url, _frag = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return parsed._replace(path=path).geturl()


def is_ignored_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in IGNORED_SCHEMES:
        return True
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in IGNORED_EXTENSIONS)


class WebsiteCrawler:
    """Crawls a single website, staying within its domain."""

    def __init__(self, start_url: str, max_pages: int = 500, max_workers: int = 5,
                 timeout: int = 15, stop_event: threading.Event = None,
                 on_status=None):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.max_pages = max_pages
        self.max_workers = max_workers
        self.timeout = timeout
        self.stop_event = stop_event or threading.Event()
        self.on_status = on_status  # callback(str)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _log(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def _fetch(self, url: str):
        """Fetch a URL. Returns the Response, or None if it should be skipped."""
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as exc:
            self._log(f"Could not fetch {url} ({exc.__class__.__name__})")
            return None

        if resp.status_code >= 400:
            self._log(f"Skipped {url} (HTTP {resp.status_code})")
            return None

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return None

        # Some servers redirect to a different domain (e.g. CDN) - stay safe.
        final_domain = urlparse(resp.url).netloc
        if final_domain and final_domain != self.domain:
            return None

        return resp

    def crawl(self):
        """Generator that yields CrawledPage objects as pages are discovered
        and fetched, expanding breadth-first, one layer at a time."""
        start_norm = normalize_url(self.start_url)
        visited = {start_norm}
        frontier = [start_norm]
        pages_done = 0

        while frontier and pages_done < self.max_pages:
            if self.stop_event.is_set():
                self._log("Scan stopped by user.")
                return

            batch = frontier[: self.max_pages - pages_done]
            frontier = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                future_to_url = {pool.submit(self._fetch, u): u for u in batch}
                for future in as_completed(future_to_url):
                    if self.stop_event.is_set():
                        break

                    url = future_to_url[future]
                    try:
                        resp = future.result()
                    except Exception as exc:  # pragma: no cover - defensive
                        self._log(f"Error fetching {url}: {exc}")
                        continue
                    if resp is None:
                        continue

                    pages_done += 1
                    html = resp.text
                    soup = BeautifulSoup(html, "lxml")
                    title_tag = soup.find("title")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    self._log(f"Fetched ({pages_done}/{self.max_pages}): {url}")
                    yield CrawledPage(url=url, status_code=resp.status_code,
                                       title=title, html=html)

                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if not href or is_ignored_link(href):
                            continue
                        absolute = urljoin(url, href)
                        if is_ignored_link(absolute):
                            continue
                        parsed = urlparse(absolute)
                        if parsed.scheme not in ("http", "https"):
                            continue
                        if parsed.netloc and parsed.netloc != self.domain:
                            continue  # external link - ignore
                        norm = normalize_url(absolute)
                        if norm not in visited:
                            visited.add(norm)
                            frontier.append(norm)

        self._log(f"Finished crawling {self.domain}: {pages_done} page(s) scanned.")
