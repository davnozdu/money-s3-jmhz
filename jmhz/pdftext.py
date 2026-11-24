"""Vytažení textu z PDF tisku JMHZ (Money S3) po řádcích, s polohou fragmentů."""
from dataclasses import dataclass
from typing import List

import pdfplumber

FOOTER_MARKERS = ("Zpracováno systémem", "Vytiskl(a):", "www.money.cz", "Strana:")
ROW_TOLERANCE = 2.0  # body; fragmenty s menším rozdílem y patří na stejný řádek


@dataclass(frozen=True)
class Chunk:
    page: int
    x: float
    y: float
    text: str


Row = List[Chunk]


class PdfTextError(Exception):
    pass


def _page_chunks(page, page_no: int) -> List[Chunk]:
    words = page.extract_words(keep_blank_chars=True, x_tolerance=1.5)
    return [Chunk(page_no, float(w["x0"]), float(w["top"]), " ".join(w["text"].split()))
            for w in words if w["text"].strip()]


def _group_rows(chunks: List[Chunk]) -> List[Row]:
    rows: List[Row] = []
    for c in sorted(chunks, key=lambda c: (c.y, c.x)):
        if rows and abs(rows[-1][0].y - c.y) <= ROW_TOLERANCE:
            rows[-1].append(c)
        else:
            rows.append([c])
    for r in rows:
        r.sort(key=lambda c: c.x)
    return rows


def _joined(row: Row) -> str:
    return " ".join(c.text for c in row)


def _is_footer(row: Row) -> bool:
    text = " ".join(c.text for c in row)
    return any(m in text for m in FOOTER_MARKERS)


def extract_rows(pdf_path: str) -> List[Row]:
    """Vrátí řádky dokumentu (stránka, y, x) bez patiček a bez opakované hlavičky firmy."""
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:  # poškozený nebo jiný soubor
        raise PdfTextError(f"Soubor nelze přečíst jako PDF: {e}") from e
    result: List[Row] = []
    company_line = None
    with pdf:
        pages = list(pdf.pages)
        page_rows = [_group_rows(_page_chunks(p, n)) for n, p in enumerate(pages)]
    for page_no, rows in enumerate(page_rows):
        rows = [r for r in rows if not _is_footer(r)]
        if page_no == 0 and len(rows) > 1:
            company_line = _joined(rows[1])
        elif rows and company_line and _joined(rows[0]) == company_line:
            rows = rows[1:]  # hlavička firmy opakovaná na každé stránce
        result.extend(rows)
    if not result:
        raise PdfTextError("PDF neobsahuje text (je to sken nebo prázdný dokument?)")
    return result
