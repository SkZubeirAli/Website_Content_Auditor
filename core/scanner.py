"""Scans a page's HTML for target words/phrases and extracts the
surrounding sentence and nearest heading for each occurrence found.
"""
import re
from dataclasses import dataclass
from bs4 import BeautifulSoup

# Block-level elements we treat as "content" worth scanning.
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th",
              "span", "blockquote", "figcaption", "a"]
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Occurrence:
    word: str          # canonical word/phrase from the word list
    matched_text: str  # the exact text matched on the page (preserves case)
    section: str        # nearest preceding heading text
    sentence: str        # sentence/snippet containing the match


def _build_pattern(word_list):
    """Combine every word/phrase into one regex, longest phrase first, so
    e.g. "Years of experience" matches before the shorter "Experience".
    Single words get an optional trailing 's'/'es' so simple plurals are
    caught even if a plural form wasn't listed explicitly."""
    entries = sorted(range(len(word_list)), key=lambda i: len(word_list[i]["word"]),
                      reverse=True)
    parts = []
    for idx in entries:
        word = word_list[idx]["word"]
        escaped = re.escape(word)
        if " " in word or "-" in word:
            pattern = escaped
        else:
            pattern = escaped + r"(?:e?s)?"
        parts.append(rf"(?P<w{idx}>\b{pattern}\b)")
    combined = "|".join(parts)
    return re.compile(combined, re.IGNORECASE)


class WordScanner:
    """Reusable scanner built once from the loaded word list, then run
    against every crawled page's HTML."""

    def __init__(self, word_list):
        self.word_list = word_list
        self._by_index = {i: entry for i, entry in enumerate(word_list)}
        self._replacements_by_word = {
            entry["word"].lower(): entry["replacements"] for entry in word_list
        }
        self.pattern = _build_pattern(word_list)

    def replacements_for(self, word: str):
        return self._replacements_by_word.get(word.lower(), [])

    def scan_html(self, html: str):
        """Returns a list of Occurrence objects found in the page, in
        document order, each tagged with the nearest preceding heading."""
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()

        occurrences = []
        current_section = ""

        for tag in soup.find_all(BLOCK_TAGS):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            # Collapse newlines/repeated whitespace from the raw HTML source
            # so phrases split across lines (e.g. "long-lasting\n  results")
            # still match as a single space-separated phrase.
            text = re.sub(r"\s+", " ", text)

            if tag.name in HEADING_TAGS:
                current_section = text

            for match in self.pattern.finditer(text):
                idx = int(match.lastgroup[1:])
                entry = self._by_index[idx]
                sentence = self._sentence_around(text, match.start(), match.end())
                occurrences.append(Occurrence(
                    word=entry["word"],
                    matched_text=match.group(),
                    section=current_section or "(no heading found)",
                    sentence=sentence,
                ))

        return occurrences

    @staticmethod
    def _sentence_around(text: str, start: int, end: int) -> str:
        sentences = SENTENCE_SPLIT_RE.split(text)
        pos = 0
        for sentence in sentences:
            s_start = pos
            s_end = pos + len(sentence)
            if s_start <= start <= s_end + 1:
                return sentence.strip()
            pos = s_end + 1
        # Fallback: a window of characters around the match.
        return text[max(0, start - 60):end + 60].strip()
