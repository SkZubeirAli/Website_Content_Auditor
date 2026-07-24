"""Quick functional sanity checks for word_list, scanner, and report -
no network required. Run with: python test_core.py
"""
from core.word_list import load_word_list
from core.scanner import WordScanner
from core.report import aggregate_rows, export_to_excel

SAMPLE_HTML = """
<html>
<head><title>About Us</title></head>
<body>
  <nav>Home About Contact</nav>
  <h1>Why Choose Us</h1>
  <p>Our expert technicians provide reliable pest control services across
  the region. With years of experience, our team is fully licensed and
  qualified to handle any infestation.</p>
  <h2>Our Approach</h2>
  <p>We are a specialist provider, and our expertise means long-lasting
  results you can trust. We are a trusted name and promise effective
  treatment every time.</p>
  <footer>Copyright 2026</footer>
</body>
</html>
"""


def main():
    word_list = load_word_list()  # default config/words.json
    print(f"Loaded {len(word_list)} word list entries.\n")

    scanner = WordScanner(word_list)
    occurrences = scanner.scan_html(SAMPLE_HTML)

    print(f"Found {len(occurrences)} occurrences:\n")
    for occ in occurrences:
        print(f"  - '{occ.matched_text}' (canonical: {occ.word}) | section: {occ.section!r}")
        print(f"      sentence: {occ.sentence!r}")

    raw_rows = []
    for occ in occurrences:
        raw_rows.append({
            "website": "freshlypestcontrol.com.au",
            "url": "https://freshlypestcontrol.com.au/about",
            "title": "About Us",
            "word": occ.word,
            "replacements": scanner.replacements_for(occ.word),
            "section": occ.section,
            "sentence": occ.sentence,
        })

    rows = aggregate_rows(raw_rows)
    print(f"\nAggregated into {len(rows)} report rows:\n")
    for r in rows:
        print(r)

    out_path = export_to_excel(rows, "/tmp/Website_Audit_Report_TEST.xlsx")
    print(f"\nExported test report to: {out_path}")

    # Basic assertions
    assert any(o.word == "Expert" for o in occurrences), "Should find 'expert'"
    assert any(o.word == "Years of experience" for o in occurrences), "Should find phrase over 'Experience'"
    assert any(o.word == "Licensed" for o in occurrences)
    assert any(o.word == "Qualified" for o in occurrences)
    assert any(o.word == "Long-lasting Results" for o in occurrences)
    assert "Home About Contact" not in [occ.sentence for occ in occurrences], "nav text should be excluded"
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
