"""Příkazová řádka: PDF tisk JMHZ z Money S3 -> XML + ZIP pro ePortál ČSSZ."""
import argparse
import os
import sys
import zipfile
from typing import List, Optional

from lxml import etree

from . import __version__
from .build import build_xml
from .checks import run_checks
from .config import load_config
from .parse import ParseError, parse_report
from .pdftext import PdfTextError, extract_rows
from .validate import SCHEMA_VERSION, validate_xsd

MESICE = ["Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec", "Srpen",
          "Září", "Říjen", "Listopad", "Prosinec"]
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jmhz.ini")


def _kc(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " Kč"


def _summary(report, xml_path: str, zip_path: str, warnings: List[str]) -> str:
    p = report.pvpoj
    lines = [
        "",
        f"JMHZ {MESICE[report.mesic - 1]} {report.rok} – {report.nazev} (IČ {report.ico})",
        f"  Variabilní symbol:                 {report.variabilni_symbol}",
        f"  Zaměstnanci:                       {len(report.employees)}",
    ]
    for e in report.employees:
        lines.append(f"    • {e.jmeno_cele} (OIČ {e.ik_mpsv}, {e.vztah}): "
                     f"VZ {_kc(e.f['vz_zec'])}, odpracováno {e.f['odprac_hod']} h")
    lines += [
        "  Rekapitulace:",
        f"    Úhrn vyměřovacích základů:       {_kc(p['zaklad_a'] + p['zaklad_b'] + p['zaklad_c'])}",
        f"    Pojistné za zaměstnavatele:      {_kc(p['pojistne_zamestnavatele'])}",
        f"    Pojistné za zaměstnance:         {_kc(p['pojistne_zamestnance'])}",
        f"    Pojistné celkem:                 {_kc(p['pojistne_celkem'])}",
        f"    Pojistné k úhradě:               {_kc(p['uhrada'])}",
        f"    Sražené zálohy na daň:           {_kc(report.dan_zaloha_po_sleve)}",
        "",
    ]
    for w in warnings:
        lines.append(f"UPOZORNĚNÍ: {w}")
    if warnings:
        lines.append("")
    lines += [
        f"Hotovo. XML ověřeno proti schématu XSD {SCHEMA_VERSION} a kontrolám ČSSZ.",
        f"  Pro ePortál nahrajte:  {zip_path}",
        f"  (XML pro kontrolu:     {xml_path})",
    ]
    return "\n".join(lines)


def run(pdf: str, config: Optional[str], out_dir: Optional[str]) -> int:
    if not os.path.isfile(pdf):
        print(f"CHYBA: soubor '{pdf}' neexistuje.")
        return 1
    try:
        cfg = load_config(config)
        report = parse_report(extract_rows(pdf))
    except (PdfTextError, ParseError, ValueError, OSError) as e:
        print(f"CHYBA: {e}")
        return 1

    issues = run_checks(report)
    errors = [i for i in issues if i.level == "error"]
    warnings = [i.zprava for i in issues if i.level == "warning"]
    tree, build_warnings = build_xml(report, cfg)
    warnings += build_warnings
    xsd_errors = validate_xsd(tree)

    if errors or xsd_errors:
        print("CHYBA: podání nebylo vytvořeno, tisk obsahuje problémy:")
        for i in errors:
            print(f"  [{i.kod}] {i.zprava}")
        for x in xsd_errors:
            print(f"  [XSD] {x}")
        return 1

    out_dir = out_dir or os.path.dirname(os.path.abspath(pdf))
    base = f"JMHZ_{report.rok}_{report.mesic:02d}"
    xml_path = os.path.join(out_dir, base + ".xml")
    zip_path = os.path.join(out_dir, base + ".zip")
    data = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    with open(xml_path, "wb") as fh:
        fh.write(data)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(base + ".xml", data)
    print(_summary(report, xml_path, zip_path, warnings))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows konzole
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(
        prog="jmhz.py",
        description="Převod PDF tisku JMHZ z Money S3 na XML/ZIP pro ePortál ČSSZ.")
    ap.add_argument("pdf", help="PDF tisk 'Jednotné měsíční hlášení zaměstnavatele' z Money S3")
    ap.add_argument("--config", help="soubor nastavení (výchozí: jmhz.ini vedle jmhz.py)")
    ap.add_argument("--out", help="složka pro výstup (výchozí: složka s PDF)")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    config = a.config or (DEFAULT_CONFIG if os.path.isfile(DEFAULT_CONFIG) else None)
    return run(a.pdf, config, a.out)
