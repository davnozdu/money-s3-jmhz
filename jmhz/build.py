"""Sestavení XML podání JMHZ (XSD 1.4.3.6) z rozebraného tisku."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, List, Optional, Tuple
import uuid as uuidlib

from lxml import etree

from . import __version__
from .config import Config
from .parse import Employee, Report

NS = {
    "n1": "http://schemas.cssz.cz/JMHZ/podani/1.0",
    "so": "http://schemas.cssz.cz/JMHZ/souhrn/1.0",
    "pvpoj": "http://schemas.cssz.cz/JMHZ/PVPOJ/1.0",
    "form": "http://schemas.cssz.cz/JMHZ/form/1.0",
}
TYP = {"Řádné": "R", "Řádný": "R", "Opravné": "O", "Opravný": "O", "Storno": "S"}
MAX_TYDENNI = Decimal("40")


def _q(prefix: str, name: str) -> str:
    return f"{{{NS[prefix]}}}{name}"


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


class _El:
    """Pomocník: necháme vzniknout prvek jen tehdy, když má obsah."""

    def __init__(self, prefix: str, name: str):
        self.el = etree.Element(_q(prefix, name))
        self.prefix = prefix

    def val(self, name: str, value, keep_zero: bool = False) -> "_El":
        """Přidá jednoduchý prvek; nulové nepovinné hodnoty vynechá (pravidla ČSSZ:
        nepovinný atribut nesmí 'nabývat hodnoty', ani 0)."""
        if value is None:
            return self
        if not isinstance(value, bool) and isinstance(value, (int, Decimal)) and value == 0 \
                and not keep_zero:
            return self
        etree.SubElement(self.el, _q(self.prefix, name)).text = _fmt(value)
        return self

    def sub(self, child: "_El") -> "_El":
        if len(child.el):
            self.el.append(child.el)
        return self

    def new(self, name: str) -> "_El":
        return _El(self.prefix, name)


def _formular(e: Employee, report: Report, cfg: Config, new_id, warnings: List[str]) -> etree._Element:
    f = e.f
    fo = etree.Element(_q("n1", "formularOsoby"))
    h = etree.SubElement(fo, _q("n1", "hlavicka"))
    etree.SubElement(h, _q("n1", "idFormulare")).text = str(new_id())
    etree.SubElement(h, _q("n1", "typFormulare")).text = TYP.get(f["typ_formulare"], f["typ_formulare"])
    etree.SubElement(h, _q("n1", "primarniPpv")).text = _fmt(e.primarni)

    bp = _El("form", "bezPriznaku")
    bp.sub(bp.new("identifikace").val("ikMpsv", e.ik_mpsv).val("idPpv", e.id_ppv))

    if e.primarni:
        sd = bp.new("souhrnDataZec")
        prijmy = sd.new("prijmy").val("zuctovanoCelkem", f["zuctovano"], keep_zero=True) \
            .val("osvobozenoCelkem", f["osvobozeno"]).val("odmenyNerezident", f["odmeny_nerez"])
        prijmy.sub(prijmy.new("prispevekZamestnavatele")
                   .val("prispevekZelSporeniOsvob", f["prisp_celkem"])
                   .val("prispevekZelPojDlPece", f["prisp_pece"])
                   .val("prispevekPenzPripoj", f["prisp_penz_pripoj"])
                   .val("prispevekDoplnPenzPripoj", f["prisp_dps"])
                   .val("prispevekPenzPoj", f["prisp_penz_poj"])
                   .val("prispevekZivotPoj", f["prisp_zivot"])
                   .val("prispevekDip", f["prisp_dip"]))
        sd.sub(prijmy)
        if f["zaklad_zalohy"]:
            sd.sub(sd.new("zalohaNaDan").val("zakladDane", f["zaklad_zalohy"], keep_zero=True)
                   .val("vypoctenaZaloha", f["vypoctena"], keep_zero=True)
                   .val("danZalohaPoSleve", f["srazena_zaloha"], keep_zero=True)
                   .val("danBonus", f["bonus"]))
        if f["zaklad_zvl"]:
            sd.sub(sd.new("zvlastniSazbaDane").val("zakladDane", f["zaklad_zvl"], keep_zero=True)
                   .val("srazenaDan", f["srazena_zvl"], keep_zero=True)
                   .val("odmenaNerezident", f["odmena_nerez_zvl"])
                   .val("srazenaDanNerezident", f["srazena_nerez"]))
        sd.val("prohlaseniPoplatnika", f["prohlaseni"])
        if f["prohlaseni"]:
            sd.sub(sd.new("prohlaseniPoplatnikaDane").val("zakladniSleva", f["sleva_poplatnik"])
                   .val("zakladniSlevaInvalidita12", f["sleva_inval12"])
                   .val("rozsirenaSlevaInvalidita3", f["sleva_inval3"])
                   .val("slevaZTPP", f["sleva_ztpp"])
                   .val("danoveZvyhodneniDetiMesic", f["zvyh_deti"])
                   .val("slevaDite", f["sleva_deti"]))
        sd.sub(sd.new("mzdaCista").val("mzdaCista", f["cisty"], keep_zero=True)
               .val("srazkyZeMzdyEvidovany", f["srazky"]))
        sd.sub(sd.new("zdravPojZamestnavatel").val("zdravotniPojisteni", f["zp_zel"], keep_zero=True))
        sd.sub(sd.new("zdravPojZamestnanec").val("zdravotniPojisteni", f["zp_zec"], keep_zero=True))
        bp.sub(sd)

    po = bp.new("pojisteni")
    po.sub(po.new("trvani").val("pojisteniOd", f["pojisteni_od"]).val("pojisteniDo", f["pojisteni_do"]))
    po.sub(po.new("vymerovaciZaklad").val("castkaOdvodPojistneho", f["vz_zec"], keep_zero=True)
           .val("prijemNepojistenaCinnost", f["prijem_vc_nepoj"], keep_zero=True))
    if f["vz_zec"]:
        po.sub(po.new("vymerovaciZakladParagraf5").val("pismenoA", f["vz_a"], keep_zero=True)
               .val("pismenoB", f["vz_b"]).val("pismenoC", f["vz_c"]))
    seznam = po.new("eldpSeznam")
    eldp = seznam.new("eldp").val("kod", f["eldp_kod"]).val("platnostOd", f["eldp_od"]) \
        .val("platnostDo", f["eldp_do"]).val("pocetDnu", f["eldp_dny"], keep_zero=True) \
        .val("vymerovaciZaklad", f["eldp_vz"], keep_zero=True)
    seznam.sub(eldp)
    po.sub(seznam)
    po.sub(po.new("pojisteniZamestnanec").val("socialniPojisteni", f["poj_zec"], keep_zero=True))
    po.sub(po.new("pojisteniZamestnavatel").val("socialniPojisteni", f["poj_zel"], keep_zero=True))
    bp.sub(po)

    tydenni = f["tydenni"]
    if tydenni > MAX_TYDENNI:
        warnings.append(f"{e.jmeno_cele}: stanovená týdenní pracovní doba v tisku je {tydenni} h, "
                        f"to je víc než zákonných 40 h – použito {cfg.tydenni_doba} h z nastavení.")
        tydenni = cfg.tydenni_doba
    obec, kod_obce, stat = e.misto
    vp = bp.new("vykonavanaPozice")
    vp.sub(vp.new("mistoVykonuPrace").val("obec", obec).val("kodObce", kod_obce).val("kodStatu", stat))
    vp.val("uplatnujiPrispevekApz", f["apz"]).val("funkcniPozitky", f["funkcni_pozitky"]) \
        .val("docasnePrideleniEvidovano", f["docasne_prideleni"])
    vp.sub(vp.new("fondPracovniDoby")
           .val("stanovenyFond", f["stanoveny_fond"], keep_zero=True)
           .val("sjednanyFond", f["sjednany_fond"], keep_zero=True)
           .val("stanovenaTydenniDoba", Decimal(tydenni).quantize(Decimal("0.01")), keep_zero=True))
    bp.sub(vp)

    pz = bp.new("prubehZamestnani")
    pz.sub(pz.new("odpracovaneDny").val("dnyEvidencniStav", f["dny_evidencni"], keep_zero=True))
    oh = pz.new("odpracovaneHodiny").val("pocet", f["odprac_hod"], keep_zero=True)
    oh.sub(oh.new("rozpad").val("prescas", f["prescas_hod"]))
    pz.sub(oh)
    if f["neodprac_celkem"]:
        pz.sub(pz.new("neodpracovaneHodiny")
               .val("hodinyNeodpracCelkem", f["neodprac_celkem"], keep_zero=True)
               .val("hodinyNeodpracNahrada", f["neodprac_nahrada"])
               .val("hodinyNeodpracBezNahrady", f["neodprac_neschop_bez"])
               .val("hodinyNeodpracNeschop", f["neodprac_neschop_nahrada"])
               .val("hodinyNeodpracDovol", f["neodprac_dovolena"])
               .val("hodinyNeodpracOcr", f["neodprac_osetrovne"]))
        pz.sub(pz.new("prekazkyVPraci").val("prekazkaZamestnanec", f["prekazky_zec"])
               .val("prekazkaZamestnavatel", f["prekazky_zel"]))
    bp.sub(pz)

    pr = bp.new("prijem")
    pr.sub(pr.new("dan").val("zakladDane", f["zaklad_dane"], keep_zero=True))
    bp.sub(pr)

    mz = bp.new("mzda").val("mzdaZuctovana", f["mzda_zuctovana"], keep_zero=True)
    if f["mzda_zuctovana"]:
        rozpad = mz.new("mzdaRozpad").val("tarif", f["tarif"], keep_zero=True) \
            .val("odmenyPravidelne", f["odmeny_prav"], keep_zero=True) \
            .val("odmenyNepravidelne", f["odmeny_neprav"], keep_zero=True)
        if f["priplatky_celkem"]:
            rozpad.sub(rozpad.new("priplatky").val("celkem", f["priplatky_celkem"])
                       .val("prescas", f["priplatky_prescas"]).val("nocni", f["priplatky_noc"])
                       .val("sobotaNedele", f["priplatky_sobota"]).val("svatek", f["priplatky_svatek"]))
        mz.sub(rozpad)
    if f["nahrady_celkem"]:
        mz.sub(mz.new("nahrady").val("mzdyZuctovane", f["nahrady_celkem"])
               .val("dovolena", f["nahrady_dovolena"]).val("svatky", f["nahrady_svatky"])
               .val("prekazkyZamestnavatel", f["nahrady_prek_zel"])
               .val("prekazkyZamestnanec", f["nahrady_prek_zec"])
               .val("docasnaNeschopnost", f["nahrady_nemoc"]))
    mz.sub(mz.new("odmeny").val("pohotovost", f["pohotovost"]))
    mz.sub(mz.new("vydelek").val("vydelekPrumernyHod", f["vydelek"], keep_zero=True))
    bp.sub(mz)

    fo.append(bp.el)
    return fo


def build_xml(report: Report, cfg: Config, now: Optional[datetime] = None,
              new_id: Callable[[], uuidlib.UUID] = uuidlib.uuid4
              ) -> Tuple[etree._ElementTree, List[str]]:
    """Vrátí (XML strom, varování)."""
    now = now or datetime.now(timezone.utc)
    warnings: List[str] = []
    root = etree.Element(_q("n1", "jmhz"), nsmap=NS)
    etree.SubElement(root, _q("n1", "VENDOR"), productName="money-s3-jmhz",
                     productVersion=__version__)
    email = cfg.email or report.email
    if email:
        etree.SubElement(root, _q("n1", "SENDER"), EmailNotifikace=email)

    count = len(report.employees)
    h = _El("n1", "hlavicka").val("idPodani", str(new_id())) \
        .val("typPodani", TYP.get(report.typ_podani, report.typ_podani)) \
        .val("variabilniSymbol", report.variabilni_symbol) \
        .val("mesic", report.mesic).val("rok", report.rok) \
        .val("datumVyplneni", now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")) \
        .val("balikPoradi", 1).val("balikyPocet", 1) \
        .val("formularePocetVBaliku", count).val("formularePocetCelkem", count)
    root.append(h.el)

    so = _El("so", "souhrn")
    so.sub(so.new("danUdajeMesic").val("danZalohaPoSleve", report.dan_zaloha_po_sleve, keep_zero=True)
           .val("danBonus", report.dan_bonus))
    root.append(so.el)

    p = report.pvpoj
    pv = _El("pvpoj", "PVPOJ")
    pojistne = pv.new("pojistne") \
        .val("zakladZamestnavateleA", p["zaklad_a"], keep_zero=True) \
        .val("pojistneZamestnavateleA", p["pojistne_a"], keep_zero=True) \
        .val("zakladZamestnavateleB", p["zaklad_b"]).val("pojistneZamestnavateleB", p["pojistne_b"]) \
        .val("zakladZamestnavateleC", p["zaklad_c"]).val("pojistneZamestnavateleC", p["pojistne_c"]) \
        .val("pojistneZamestnavateleCelkem", p["pojistne_zamestnavatele"], keep_zero=True) \
        .val("pojistneZamestnance", p["pojistne_zamestnance"], keep_zero=True) \
        .val("pojistneCelkem", p["pojistne_celkem"], keep_zero=True)
    pv.sub(pojistne)
    for name, prefix in (("slevaZamestnavatele", "sleva_zel"), ("slevyZamestnancu", "sleva_duch"),
                         ("slevyZamestnancuOvoZel", "sleva_ovo")):
        if p[f"{prefix}_pocet"]:
            pv.sub(pv.new(name).val("pocetZamestnancu", p[f"{prefix}_pocet"], keep_zero=True)
                   .val("uhrnVymerovacichZakladu", p[f"{prefix}_uhrn"], keep_zero=True)
                   .val("pojistneSleva", p[prefix], keep_zero=True))
    pv.val("pojistneUhrada", p["uhrada"], keep_zero=True)
    root.append(pv.el)

    fos = etree.SubElement(root, _q("n1", "formulareOsob"))
    for e in report.employees:
        fos.append(_formular(e, report, cfg, new_id, warnings))
    return etree.ElementTree(root), warnings
