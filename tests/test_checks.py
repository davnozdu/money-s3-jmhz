import json
import os
from datetime import date
from decimal import Decimal

import pytest

from jmhz.checks import run_checks
from jmhz.parse import parse_report, rows_from_json
from jmhz.pdftext import extract_rows

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _report():
    with open(os.path.join(FIXTURES, "synthetic_rows.json"), encoding="utf-8") as fh:
        return parse_report(rows_from_json(json.load(fh)))


def _errors(report):
    return [i for i in run_checks(report) if i.level == "error"]


def _codes(report):
    return {i.kod for i in _errors(report)}


def test_synthetic_clean():
    assert _errors(_report()) == []


def test_real_pdfs_clean(real_pdfs):
    for p in real_pdfs:
        errs = _errors(parse_report(extract_rows(p)))
        assert errs == [], (p, errs)


def _mut(fn):
    r = _report()
    fn(r)
    return _codes(r)


@pytest.mark.parametrize("code,mutate", [
    ("K4", lambda r: r.pvpoj.update(uhrada=1)),
    ("K7", lambda r: r.pvpoj.update(zaklad_a=14601)),
    ("K8", lambda r: r.pvpoj.update(pojistne_a=3620)),
    ("K11", lambda r: r.pvpoj.update(pojistne_zamestnavatele=1)),
    ("K13", lambda r: r.pvpoj.update(pojistne_celkem=1)),
    ("K168", lambda r: r.pvpoj.update(pojistne_zamestnance=900)),
    ("K118", lambda r: r.employees[0].f.update(poj_zec=518)),
    ("K315", lambda r: r.employees[0].f.update(poj_zel=1810)),
    ("K216", lambda r: r.employees[0].f.update(vz_a=7000)),
    ("K20", lambda r: r.employees[0].f.update(prescas_hod=Decimal("50"))),
    ("K23", lambda r: r.employees[0].f.update(neodprac_dovolena=Decimal("5"))),
    ("K58", lambda r: r.employees[0].f.update(eldp_dny=32)),
    ("K99", lambda r: r.employees[0].f.update(eldp_od=date(2026, 2, 1))),
    ("K100", lambda r: r.employees[0].f.update(eldp_od=date(2026, 3, 31), eldp_do=date(2026, 3, 1))),
    ("K134", lambda r: r.employees[0].f.update(pojisteni_od=date(2026, 3, 15))),
    ("K74", lambda r: r.employees[0].f.update(bonus=20)),
    ("K97", lambda r: r.employees[0].f.update(osvobozeno=99999)),
    ("HODINY", lambda r: r.employees[0].f.update(odprac_hod=Decimal("241"))),
    ("PPV", lambda r: r.employees[1].f.update(ik_mpsv="1000000001")),
    ("NEPODPOROVANO", lambda r: setattr(r, "typ_podani", "Opravné")),
    ("NEPODPOROVANO", lambda r: setattr(r, "specificka_skutecnost", "Úmrtí")),
    ("NEPODPOROVANO", lambda r: r.employees[0].f.update(sleva_zel=True)),
    ("NEPODPOROVANO", lambda r: r.employees[0].f.update(zvyh_deti=1267)),
    ("NEPODPOROVANO", lambda r: r.employees[0].f.update(riziko_hod=Decimal("3"))),
    ("NEPODPOROVANO", lambda r: r.employees[0].eldp_dny_detail.update({"Dny nemoci": 3})),
])
def test_check_fires(code, mutate):
    assert code in _mut(mutate)


def test_pvpoj_rounds_total_not_sum_of_employees():
    # 2 × 7 300: zaměstnavatel 3 621 (ne 2 × 1 811 = 3 622) – zaokrouhluje se úhrn
    assert _report().pvpoj["pojistne_a"] == 3621
    assert "K8" not in _codes(_report())
