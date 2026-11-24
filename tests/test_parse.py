import json
import re
import os
from datetime import date
from decimal import Decimal

import pytest

from conftest import pdf_for
from jmhz.parse import ParseError, num, parse_report, rows_from_json
from jmhz.pdftext import extract_rows

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_num_formats():
    assert num("7 300") == Decimal("7300")
    assert num("165,910") == Decimal("165.910")
    assert num("2,00") == Decimal("2.00")
    assert num("-1 234,5") == Decimal("-1234.5")
    with pytest.raises(ValueError):
        num("abc")


def test_october_real():
    r = parse_report(extract_rows(pdf_for("102027")))
    assert (r.mesic, r.rok) == (10, 2026)
    assert re.fullmatch(r"\d{10}", r.variabilni_symbol)
    assert r.typ_podani == "Řádné"
    assert r.specificka_skutecnost is None
    assert r.pvpoj["zaklad_a"] == 7300
    assert r.pvpoj["pojistne_a"] == 1811
    assert r.pvpoj["pojistne_zamestnance"] == 519
    assert r.pvpoj["pojistne_celkem"] == 2330
    assert r.pvpoj["uhrada"] == 2330
    assert r.dan_zaloha_po_sleve == 0
    assert len(r.employees) == 1
    e = r.employees[0]
    assert re.fullmatch(r"\d{10}", e.ik_mpsv)
    assert re.fullmatch(r"\d{13}", e.id_ppv)
    assert e.druh_cinnosti == "A"
    assert e.primarni is True
    assert e.f["odprac_hod"] == Decimal("42.00")
    assert e.f["riziko_hod"] == Decimal("0.00")
    assert e.f["neodprac_celkem"] == Decimal("2.00")
    assert e.f["tydenni"] == Decimal("99.00")
    assert e.f["eldp_kod"] == "A++"
    assert e.f["eldp_dny"] == 31
    assert e.f["eldp_od"] == date(2026, 10, 1)
    assert e.f["eldp_do"] == date(2026, 10, 31)
    assert e.f["pojisteni_od"] == date(2026, 10, 1)
    assert e.f["eldp_vz"] == 7300
    assert e.f["cisty"] == 5773
    assert e.f["srazky"] is False
    assert e.f["zp_zel"] == 2016
    assert e.f["zp_zec"] == 1008
    assert e.f["vydelek"] == Decimal("165.910")
    assert e.f["zaklad_zalohy"] == 7300
    assert e.f["vypoctena"] == 1095
    assert e.f["sleva_poplatnik"] == 2570
    assert e.f["prohlaseni"] is True
    obec, kod, stat = e.misto
    assert obec and re.fullmatch(r"\d{6}", kod) and stat == "CZ"


def test_april_real_old_layout():
    r = parse_report(extract_rows(pdf_for("042026")))
    assert (r.mesic, r.rok) == (4, 2026)
    e = r.employees[0]
    assert e.f["neodprac_celkem"] == Decimal("4.00")
    assert e.f["vydelek"] == Decimal("171.090")
    assert e.f["cisty"] == 5773


def test_all_real_parse(real_pdfs):
    for p in real_pdfs:
        r = parse_report(extract_rows(p))
        assert len(r.employees) == 1, p


def _synthetic():
    with open(os.path.join(FIXTURES, "synthetic_rows.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_synthetic_two_employees():
    r = parse_report(rows_from_json(_synthetic()))
    assert (r.mesic, r.rok) == (3, 2026)
    assert [e.ik_mpsv for e in r.employees] == ["1000000001", "1000000002"]
    assert r.employees[1].f["odprac_hod"] == Decimal("160.00")


def test_missing_field_names_it():
    data = _synthetic()
    data = [row for row in data if not any(c[3] == "Čistý příjem:" for c in row)]
    with pytest.raises(ParseError) as ei:
        parse_report(rows_from_json(data))
    assert "Čistý příjem" in str(ei.value)


def test_not_jmhz():
    with pytest.raises(ParseError):
        parse_report(rows_from_json([[[0, 20, 20, "Faktura č. 123"]]]))
