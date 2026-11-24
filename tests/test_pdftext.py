from jmhz.pdftext import extract_rows


def _texts(row):
    return " ".join(c.text for c in row)


def test_first_row_is_title_and_footers_removed(real_pdfs):
    for path in real_pdfs:
        rows = extract_rows(path)
        assert "Jednotné měsíční hlášení zaměstnavatele" in _texts(rows[0]), path
        for row in rows:
            t = _texts(row)
            assert "Strana:" not in t
            assert "Zpracováno systémem" not in t


def test_rows_ordered_and_chunks_left_to_right(real_pdfs):
    rows = extract_rows(real_pdfs[0])
    keys = [(r[0].page, r[0].y) for r in rows]
    assert keys == sorted(keys)
    for r in rows:
        xs = [c.x for c in r]
        assert xs == sorted(xs)


def test_company_header_only_once(real_pdfs):
    for path in real_pdfs:
        rows = extract_rows(path)
        assert sum(1 for r in rows if any(c.text.startswith("IČ:") for c in r)) == 1, path
