![Python](https://img.shields.io/badge/Python-3.12-blue)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green)
![Requests](https://img.shields.io/badge/Requests-Web%20Scraping-orange)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-brightgreen)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-blueviolet)
![OpenPyXL](https://img.shields.io/badge/OpenPyXL-Excel-success)

# Website Content Auditor

A desktop tool that crawls your WordPress websites, finds words/phrases you
want to improve for SEO and content quality, suggests better alternatives,
and exports everything to an Excel report — **it never edits your site**.
You review the report and make changes manually.

# Tech Stack
`HTML` `Python` `XML` `Tkinter` `Requests` `BeautifulSoup4` `lxml` `Pandas` 
`OpenPyXL` `Regex`  `Desktop GUI` `Web Scraping` `Excel Automation` 

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.9+. Tested with the dependency versions in
`requirements.txt`.

## How to use it

1. Paste one or more website URLs into the top box (one per line).
2. Optionally click **Load Word List...** to use a different word list
   file (defaults to `config/words.json`).
3. Click **Start Scan**. The app crawls each site's internal pages,
   scans every page's text, and fills the results table live.
4. Click **Stop Scan** any time to cancel — pages already fetched stay
   in the results.
5. Click **Export to Excel** to save `Website_Audit_Report.xlsx`.
6. Double-click any row to open that exact page in your browser.

## Project structure

```
website_content_auditor/
├── main.py                 entry point
├── requirements.txt
├── config/
│   └── words.json          editable word list + suggested replacements
├── core/
│   ├── word_list.py         loads/validates config/words.json
│   ├── crawler.py            same-domain crawler (discovery + fetching)
│   ├── scanner.py            regex word/phrase matching + context extraction
│   └── report.py             aggregation + Excel export
├── gui/
│   └── app.py                Tkinter desktop UI, threading, results table
└── test_core.py              offline sanity check for scanner/report
```

### Why this structure
Each piece is independent and swappable:
- **crawler.py** doesn't know about the word list at all — it just yields pages.
- **scanner.py** doesn't know about the network — you can feed it any HTML.
- **report.py** doesn't know about crawling or scanning — it just turns
  rows into an Excel file.
- **gui/app.py** wires the three together and handles threading so the
  window never freezes during a scan.

This means you (or a future developer) can swap the GUI for a CLI, or
swap Tkinter for PySide6, without touching the crawling/scanning logic.

## Editing the word list

Open `config/words.json` in any text editor. Each entry looks like:

```json
{"word": "Expert", "replacements": ["capable team", "dedicated team", "our team"]}
```

- Add a new object to search for a new word/phrase.
- Add/remove strings in `replacements` to change the suggestions shown.
- Multi-word phrases (like `"Years of experience"`) are matched literally
  and are automatically checked *before* shorter overlapping words (like
  `"Experience"`), so phrases don't get "eaten" by a shorter match.
- Single words automatically also match a simple trailing `s`/`es` plural
  (e.g. an entry for `"Chair"` also matches `"Chairs"`), so you generally
  only need to list plural forms separately when the suggested replacement
  text is genuinely different (as with `Expert`/`Experts` vs `Expertise`).
- Matching is always case-insensitive.

## How matching & context extraction works

For each page, the scanner walks the parsed HTML in document order over
headings, paragraphs, list items, table cells, links, etc. (`<script>`,
`<style>`, `<nav>`, and `<footer>` are ignored so menus/boilerplate don't
pollute results). It keeps track of the most recent heading (`<h1>`–`<h6>`)
seen so far as the current "section," and for every match it records the
sentence the match appeared in.

The results table (and the exported Excel file) group multiple matches of
the *same word, on the same page, under the same heading* into a single
row with an occurrence count — matching the report format in the original
spec (e.g. "Expert — 3 — Why Choose Us"). If the same word also appears
under a different heading further down the page, that's a separate row,
since it's genuinely a different section of content.

## Crawling behavior

- Breadth-first, same-domain only (external links are ignored).
- Skips images, PDFs, CSS, JS, fonts, archives, and other media by file
  extension, plus `mailto:`/`tel:`/`javascript:` links.
- Normalizes URLs (ignores `#fragments` and trailing slashes) to avoid
  scanning the same page twice.
- Skips pages that return an error status (404, 500, etc.) and keeps going.
- Fetches pages within each crawl "layer" concurrently (thread pool) so
  larger sites scan noticeably faster, while still responding to Stop
  immediately.
- Default cap of 500 pages per site (`WebsiteCrawler(max_pages=...)`) —
  plenty for a ~16-page site, adjustable in `core/crawler.py` if needed.

**Note on bot protection:** some WordPress hosts sit behind Cloudflare or
similar protection that can block automated requests, especially from
cloud/datacenter IP ranges. Running the tool from a normal
office/residential connection (as intended) should work fine; if a
particular site still blocks it, that site's WAF settings are the cause,
not the crawler logic.

## Testing without touching a live site

```bash
python test_core.py
```

This feeds a synthetic HTML page through the real scanner/report code
(no network needed) and prints/verifies the matches, sections, sentences,
and a sample Excel export — useful for checking word-list changes before
running a real scan.

## Roadmap (structured so these are easy to add later)

- `sitemap.xml` and `robots.txt` awareness — plug into `crawler.py`'s
  discovery step alongside `<a href>` link discovery.
- Regex-based search entries — `scanner._build_pattern` already isolates
  pattern-building in one place.
- Search-and-replace preview — the raw `Occurrence` objects already carry
  exact matched text and position; a preview view would reuse them as-is.
- CSV/PDF export — add alongside `report.export_to_excel` using the same
  aggregated row format.
- Dark mode — swap the `ttk.Style` theme in `gui/app.py:main()`.
- Scan history / compare two scans — persist `raw_rows`/`result_rows` to
  a local SQLite or JSON file between runs.
- Scan only selected pages / filter by page type — add a pre-crawl page
  list step (e.g. from a discovered sitemap) with checkboxes in the GUI.
- Word frequency statistics — `aggregate_rows` already computes per-word
  counts; a summary tab could reuse it grouped by word only, across pages.
