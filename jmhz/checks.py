"""Logické kontroly podle Katalogu kontrol MH (ČSSZ/MPSV, verze 1.4.2.11).

Kód 'K<n>' odpovídá ID kontroly v katalogu. Ostatní kódy jsou vlastní kontroly převodníku.
"""
import calendar
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import List

from .parse import Report

# Sazby pojistného (Katalog kontrol, list "Parametrické konstanty")
RATES = {
    # rok: (zaměstnavatel § 5a/1 a), b) záchranáři, c) riziková, zaměstnanec)
    2025: (Decimal("0.248"), Decimal("0.288"), Decimal("0.268"), Decimal("0.071")),
    2026: (Decimal("0.248"), Decimal("0.298"), Decimal("0.278"), Decimal("0.071")),
}
MAX_HODIN = Decimal("240")
MIN_BONUS = 50
# Druhy činnosti zpracovávané jiným datovým scénářem než "bez příznaku"
JINY_SCENAR = set("KLMNOPQRS")


@dataclass
class Issue:
    level: str  # "error" | "warning"
    kod: str
    zprava: str


def _ceil(x: Decimal) -> int:
    return int(x.quantize(Decimal("1"), rounding=ROUND_CEILING))


def run_checks(r: Report) -> List[Issue]:
    out: List[Issue] = []

    def err(kod, msg):
        out.append(Issue("error", kod, msg))

    def warn(kod, msg):
        out.append(Issue("warning", kod, msg))

    # ---- co převodník neumí (raději odmítnout než podat špatně)
    if r.typ_podani != "Řádné":
        err("NEPODPOROVANO", f"Typ podání '{r.typ_podani}' – převodník umí jen řádné podání.")
    if r.specificka_skutecnost:
        err("NEPODPOROVANO", "Specifická právní skutečnost – podejte ručně na ePortálu.")
    for p in ("sleva_zel_pocet", "sleva_duch_pocet", "sleva_ovo_pocet"):
        if r.pvpoj[p]:
            err("NEPODPOROVANO", "Slevy na pojistném – převodník je nepodporuje.")
            break

    if r.rok in RATES:
        ra, rb, rc, rz = RATES[r.rok]
    else:
        ra, rb, rc, rz = RATES[max(RATES)]
        warn("SAZBY", f"Sazby pojistného pro rok {r.rok} nejsou ověřené, použity sazby {max(RATES)}.")

    # ---- souhrnná část (PVPOJ)
    p = r.pvpoj
    if p["uhrada"] != p["pojistne_celkem"] - p["sleva_zel"] - p["sleva_duch"] - p["sleva_ovo"]:
        err("K4", "Pojistné k úhradě neodpovídá pojistnému celkem minus slevy.")
    if p["zaklad_a"] != sum(e.f["vz_a"] for e in r.employees):
        err("K7", "Úhrn vyměřovacích základů (standardní) ≠ součet základů zaměstnanců.")
    if p["zaklad_b"] != sum(e.f["vz_b"] for e in r.employees):
        err("K9", "Úhrn vyměřovacích základů (záchranáři) ≠ součet základů zaměstnanců.")
    for kod, zaklad, poj, rate in (("K8", "zaklad_a", "pojistne_a", ra),
                                   ("K10", "zaklad_b", "pojistne_b", rb),
                                   ("K167", "zaklad_c", "pojistne_c", rc)):
        expected = _ceil(Decimal(p[zaklad]) * rate)
        if p[poj] != expected:
            err(kod, f"Pojistné za zaměstnavatele {p[poj]} Kč ≠ {rate} × {p[zaklad]} = {expected} Kč.")
    if p["pojistne_zamestnavatele"] != p["pojistne_a"] + p["pojistne_b"] + p["pojistne_c"]:
        err("K11", "Pojistné za zaměstnavatele celkem ≠ součet dílčích částek.")
    if p["pojistne_celkem"] != p["pojistne_zamestnavatele"] + p["pojistne_zamestnance"]:
        err("K13", "Pojistné celkem ≠ za zaměstnavatele + za zaměstnance.")
    zaklady = Decimal(p["zaklad_a"] + p["zaklad_b"] + p["zaklad_c"])
    # K168: |rz × úhrn základů − pojistné zaměstnanců| <= 100 Kč (nebo 1 %)
    rozdil = abs(zaklady * rz - p["pojistne_zamestnance"])
    if rozdil > 100 and (not p["pojistne_zamestnance"]
                         or rozdil / p["pojistne_zamestnance"] > Decimal("0.01")):
        err("K168", f"Pojistné za zaměstnance {p['pojistne_zamestnance']} Kč neodpovídá "
                    f"{rz} × úhrn základů {zaklady} Kč.")

    # ---- zaměstnanci
    days = calendar.monthrange(r.rok, r.mesic)[1]
    primarni = Counter(e.ik_mpsv for e in r.employees if e.primarni)
    for oic, n in primarni.items():
        if n > 1:
            err("PPV", f"OIČ {oic}: více než jeden primární pracovněprávní vztah.")
    for oic in {e.ik_mpsv for e in r.employees} - set(primarni):
        warn("PPV", f"OIČ {oic}: žádný primární pracovněprávní vztah.")

    for e in r.employees:
        f, kdo = e.f, f"{e.jmeno_cele}: "
        # nepodporované situace
        if e.druh_cinnosti in JINY_SCENAR:
            err("NEPODPOROVANO", kdo + f"druh činnosti {e.druh_cinnosti} (jiný datový scénář).")
        if f["typ_formulare"] != "Řádný":
            err("NEPODPOROVANO", kdo + f"typ formuláře '{f['typ_formulare']}'.")
        for key, what in (("sleva_zel", "sleva na pojistném zaměstnavatele"),
                          ("sleva_duchodce", "sleva pracující důchodce"),
                          ("sleva_ovo", "sleva ovocnáři/zelináři"), ("ozp", "OZP na chráněném trhu"),
                          ("apz", "nástroj APZ"), ("docasne_prideleni", "dočasné přidělení"),
                          ("typ_odlozeneho", "odložený příjem")):
            if f[key]:
                err("NEPODPOROVANO", kdo + what + ".")
        for key, what in (("zvyh_deti", "daňové zvýhodnění na děti (chybí údaje o dětech)"),
                          ("riziko_hod", "riziková práce"), ("odecitane_celkem", "odečítané doby"),
                          ("vyloucene_celkem", "vyloučené doby"),
                          ("vyloucene_nem_celkem", "vyloučené dny")):
            if f[key]:
                err("NEPODPOROVANO", kdo + what + ".")
        if f["smeny"] not in (None, "", "0/0"):
            err("NEPODPOROVANO", kdo + "hlubinné hornictví.")
        if any(e.eldp_dny_detail.values()) or e.eldp_count > 1:
            err("NEPODPOROVANO", kdo + "ELDP s vyloučenými/odečítanými dny nebo více řádků ELDP.")

        # výpočty pojistného
        if f["vz_zec"] != f["vz_a"] + f["vz_b"] + f["vz_c"]:
            err("K216", kdo + "vyměřovací základ ≠ součet standardní + záchranáři + riziková.")
        if f["poj_zec"] != _ceil(Decimal(f["vz_zec"]) * rz):
            err("K118", kdo + f"pojistné zaměstnance {f['poj_zec']} Kč ≠ {rz} × {f['vz_zec']}.")
        exp_zel = _ceil(Decimal(f["vz_a"]) * ra) + _ceil(Decimal(f["vz_b"]) * rb) \
            + _ceil(Decimal(f["vz_c"]) * rc)
        if f["poj_zel"] != exp_zel:
            err("K315", kdo + f"pojistné zaměstnavatele {f['poj_zel']} Kč ≠ vypočtených {exp_zel} Kč.")
        if f["osvobozeno"] > f["zuctovano"]:
            err("K97", kdo + "osvobozené příjmy jsou vyšší než zúčtovaný příjem.")

        # hodiny
        if f["prescas_hod"] > f["odprac_hod"]:
            err("K20", kdo + "přesčasových hodin je víc než odpracovaných.")
        if f["neodprac_dovolena"] > f["neodprac_nahrada"]:
            err("K23", kdo + "hodiny dovolené převyšují hodiny s náhradou mzdy.")
        if f["odprac_hod"] > MAX_HODIN:
            err("HODINY", kdo + f"odpracováno {f['odprac_hod']} h, maximum je {MAX_HODIN} h.")

        # ELDP
        if f["eldp_dny"] > days:
            err("K58", kdo + f"{f['eldp_dny']} dní pojištění, měsíc má {days} dní.")
        od, do = f["eldp_od"], f["eldp_do"]
        if (od.year, od.month) != (r.rok, r.mesic) or (do.year, do.month) != (r.rok, r.mesic):
            err("K99", kdo + "platnost kódu ELDP neodpovídá hlášenému měsíci.")
        if od > do:
            err("K100", kdo + "platnost kódu ELDP od je po datu do.")
        if f["eldp_dny"] > (f["pojisteni_do"] - f["pojisteni_od"]).days + 1:
            err("K134", kdo + "počet dnů pojištění neodpovídá datům trvání pojištění.")

        # daň
        if 0 < f["bonus"] < MIN_BONUS or f["bonus"] < 0:
            err("K74", kdo + f"daňový bonus musí být 0 nebo alespoň {MIN_BONUS} Kč.")
    return out
