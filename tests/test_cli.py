import os
import shutil
import zipfile

from lxml import etree

from conftest import pdf_for
from jmhz.cli import main
from jmhz.validate import validate_xsd


def test_real_pdf_creates_xml_and_zip(tmp_path, capsys):
    src = pdf_for("092027")
    rc = main([src, "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    xml = tmp_path / "JMHZ_2026_09.xml"
    zp = tmp_path / "JMHZ_2026_09.zip"
    assert xml.exists() and zp.exists()
    with zipfile.ZipFile(zp) as z:
        assert z.namelist() == ["JMHZ_2026_09.xml"]
        tree = etree.fromstring(z.read("JMHZ_2026_09.xml")).getroottree()
    assert validate_xsd(tree) == []
    assert "2 330" in out  # pojistné celkem v rekapitulaci
    assert "Září 2026" in out
    assert "UPOZORNĚNÍ" in out  # týdenní doba 99 h


def test_broken_file_writes_nothing(tmp_path, capsys):
    bad = tmp_path / "spatny.pdf"
    bad.write_bytes(b"%PDF-1.4 tohle neni pdf")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    rc = main([str(bad), "--out", str(out_dir)])
    assert rc == 1
    assert list(out_dir.iterdir()) == []
    assert "CHYBA" in capsys.readouterr().out


def test_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "neni.pdf")]) == 1


def test_default_output_next_to_pdf(tmp_path):
    src = pdf_for("102027")
    copy = tmp_path / "rijen.pdf"
    shutil.copy(src, copy)
    assert main([str(copy)]) == 0
    assert (tmp_path / "JMHZ_2026_10.zip").exists()
