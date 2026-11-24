import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from lxml import etree

from jmhz.build import NS, build_xml
from jmhz.config import Config, load_config
from jmhz.parse import parse_report, rows_from_json
from jmhz.pdftext import extract_rows
from jmhz.validate import validate_xsd

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = datetime(2026, 4, 10, 8, 0, 0, tzinfo=timezone.utc)


def _report():
    with open(os.path.join(FIXTURES, "synthetic_rows.json"), encoding="utf-8") as fh:
        return parse_report(rows_from_json(json.load(fh)))


def _uuids():
    n = iter(range(1, 1000))
    return lambda: uuid.UUID(int=next(n))


def _build(report, cfg=None):
    return build_xml(report, cfg or Config(), NOW, _uuids())


def _x(tree, path):
    return tree.getroot().xpath(path, namespaces=NS)


def test_synthetic_is_xsd_valid():
    tree, _ = _build(_report())
    assert validate_xsd(tree) == []


def test_header_values():
    tree, _ = _build(_report())
    assert _x(tree, "string(n1:hlavicka/n1:mesic)") == "3"
    assert _x(tree, "string(n1:hlavicka/n1:rok)") == "2026"
    assert _x(tree, "string(n1:hlavicka/n1:variabilniSymbol)") == "9999999999"
    assert _x(tree, "string(n1:hlavicka/n1:typPodani)") == "R"
    assert _x(tree, "string(n1:hlavicka/n1:formularePocetCelkem)") == "2"
    assert _x(tree, "string(n1:SENDER/@EmailNotifikace)") == "mzdy@example.cz"
    assert _x(tree, "string(pvpoj:PVPOJ/pvpoj:pojistne/pvpoj:zakladZamestnavateleA)") == "14600"
    assert _x(tree, "string(pvpoj:PVPOJ/pvpoj:pojistneUhrada)") == "4658"


def test_employee_values():
    tree, _ = _build(_report())
    f = _x(tree, "n1:formulareOsob/n1:formularOsoby[1]/form:bezPriznaku")[0]
    g = lambda p: f.xpath("string(" + p + ")", namespaces=NS)  # noqa: E731
    assert g("form:identifikace/form:ikMpsv") == "1000000001"
    assert g("form:pojisteni/form:eldpSeznam/form:eldp/form:kod") == "A++"
    assert g("form:pojisteni/form:eldpSeznam/form:eldp/form:pocetDnu") == "31"
    assert g("form:pojisteni/form:eldpSeznam/form:eldp/form:platnostOd") == "2026-03-01"
    assert g("form:vykonavanaPozice/form:mistoVykonuPrace/form:kodObce") == "582786"
    assert g("form:prubehZamestnani/form:odpracovaneHodiny/form:pocet") == "42.00"
    assert g("form:prubehZamestnani/form:neodpracovaneHodiny/form:hodinyNeodpracCelkem") == "2.00"
    assert g("form:mzda/form:vydelek/form:vydelekPrumernyHod") == "165.910"
    assert g("form:souhrnDataZec/form:zalohaNaDan/form:danZalohaPoSleve") == "0"
    assert g("form:pojisteni/form:vymerovaciZaklad/form:castkaOdvodPojistneho") == "7300"


def test_zero_bonus_and_zero_optionals_omitted():
    tree, _ = _build(_report())
    assert _x(tree, "//form:danBonus") == []
    assert _x(tree, "//so:danBonus") == []
    assert _x(tree, "//form:prescas") == []  # přesčas 0
    assert _x(tree, "//form:zvlastniSazbaDane") == []
    assert _x(tree, "//form:nahrady") == []


def test_no_unworked_hours_block_when_zero():
    r = _report()
    for k in ("neodprac_celkem", "neodprac_nahrada"):
        r.employees[0].f[k] = Decimal("0")
    tree, _ = _build(r)
    blocks = _x(tree, "n1:formulareOsob/n1:formularOsoby[1]//form:neodpracovaneHodiny")
    assert blocks == []
    assert validate_xsd(tree) == []


def test_weekly_hours_99_replaced_with_config():
    tree, warnings = _build(_report(), Config(tydenni_doba=Decimal("40")))
    vals = _x(tree, "//form:stanovenaTydenniDoba/text()")
    assert vals == ["40.00", "40.00"]
    assert any("99" in w for w in warnings)


def test_deterministic():
    a = etree.tostring(_build(_report())[0])
    b = etree.tostring(_build(_report())[0])
    assert a == b


def test_load_config_ini(tmp_path):
    p = tmp_path / "jmhz.ini"
    p.write_text("[jmhz]\ntydenni_doba = 37,5\nemail = x@example.cz\n", encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg.tydenni_doba == Decimal("37.5")
    assert cfg.email == "x@example.cz"
    assert load_config(None) == Config()


def test_real_pdfs_xsd_valid(real_pdfs):
    for p in real_pdfs:
        tree, _ = build_xml(parse_report(extract_rows(p)), Config(), NOW, _uuids())
        assert validate_xsd(tree) == [], p
