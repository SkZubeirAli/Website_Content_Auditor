"""Aggregates raw scan occurrences into report rows and exports them to
an Excel workbook (Website_Audit_Report.xlsx)."""
from collections import defaultdict
import pandas as pd

COLUMNS = ["Website", "URL", "Page Title", "Word Found", "Occurrences",
           "Suggested Replacement", "Section", "Matching Sentence"]


def aggregate_rows(raw_rows):
    """raw_rows: list of dicts with keys:
        website, url, title, word, replacements, section, sentence

    Groups multiple occurrences of the same word, on the same page, under
    the same heading/section into a single row with an occurrence count -
    matching the report format requested (one row per word-per-section,
    with a running count rather than one row per single character match).
    """
    groups = defaultdict(lambda: {"count": 0, "sentences": [], "replacements": [], "title": ""})
    order = []

    for row in raw_rows:
        key = (row["website"], row["url"], row["word"], row["section"])
        if key not in groups:
            order.append(key)
        g = groups[key]
        g["count"] += 1
        if row["sentence"] and row["sentence"] not in g["sentences"]:
            g["sentences"].append(row["sentence"])
        g["title"] = row["title"]
        g["replacements"] = row["replacements"]

    table = []
    for key in order:
        website, url, word, section = key
        g = groups[key]
        sentence_preview = " | ".join(g["sentences"][:3])
        table.append({
            "Website": website,
            "URL": url,
            "Page Title": g["title"],
            "Word Found": word,
            "Occurrences": g["count"],
            "Suggested Replacement": ", ".join(g["replacements"]) if g["replacements"] else "",
            "Section": section,
            "Matching Sentence": sentence_preview,
        })
    return table


def export_to_excel(rows, filepath: str):
    """Writes the aggregated rows to an .xlsx file with readable column
    widths. `rows` should already be in the COLUMNS shape (see aggregate_rows)."""
    df = pd.DataFrame(rows, columns=COLUMNS)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Audit Report")
        worksheet = writer.sheets["Audit Report"]
        for i, col in enumerate(COLUMNS, start=1):
            if df.empty:
                max_len = len(col)
            else:
                max_len = max([len(str(col))] + [len(str(v)) for v in df[col].astype(str)])
            col_letter = worksheet.cell(row=1, column=i).column_letter
            worksheet.column_dimensions[col_letter].width = min(max_len + 2, 60)
    return filepath
