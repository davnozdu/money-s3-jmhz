"""Rozbor řádků tisku JMHZ z Money S3 na strukturovaná data."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from .pdftext import Chunk, Row

TITLE = "Jednotné měsíční hlášení zaměstnavatele"
MONTHS = {
    "leden": 1, "únor": 2, "březen": 3, "duben": 4, "květen": 5, "červen": 6,
    "červenec": 7, "srpen": 8, "září": 9, "říjen": 10, "listopad": 11, "prosinec": 12,
}
EMPLOYEE_START = re.compile(r"^(\d{5})\s+(.+)$")


class ParseError(Exception):
    pass


# ---------------------------------------------------------------- převody hodnot

def num(s: str) -> Decimal:
    """'7 300' -> 7300, '165,910' -> 165.910; jednotky se odstraní předem."""
    t = s.replace(" ", " ").replace(" ", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        raise ValueError(f"'{s}' není číslo")


def yesno(s: str) -> bool:
    t = s.strip().lower()
    if t == "ano":
        return True
    if t == "ne":
        return False
    raise ValueError(f"'{s}' není Ano/Ne")


def date_cz(s: str) -> date:
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s.strip())
    if not m:
        raise ValueError(f"'{s}' není datum")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def date_range(s: str) -> Tuple[date, date]:
    parts = [p.strip() for p in s.split(" - ")]
    if len(parts) != 2:
        raise ValueError(f"'{s}' není rozsah dat")
    return date_cz(parts[0]), date_cz(parts[1])


UNITS = {"Kč", "hod.", "dní", "směn"}


# ---------------------------------------------------------------- páry popisek: hodnota

@dataclass
class Pair:
    label: str
    values: List[str]
    chunk: Chunk


def _split_inline(c: Chunk) -> Tuple[Optional[str], Optional[str]]:
    """'IČ: 12345678' -> ('IČ', '12345678'); 'Typ podání:' -> ('Typ podání', None)."""
    if c.text.endswith(":"):
        return c.text[:-1].strip(), None
    m = re.match(r"^([^:]{1,60}):\s+(.+)$", c.text)
    if m and not re.match(r"^\d", m.group(1)):
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _pairs(rows: List[Row]) -> List[Pair]:
    pairs: List[Pair] = []
    orphans: List[Chunk] = []  # fragmenty bez popisky na řádku (víceřádkové popisky)
    for row in rows:
        current: Optional[Pair] = None
        for c in row:
            label, inline = _split_inline(c)
            if label is not None:
                current = Pair(label, [inline] if inline else [], c)
                pairs.append(current)
            elif current is not None:
                if c.text not in UNITS:
                    current.values.append(c.text)
            else:
                orphans.append(c)
    # Popiska bez hodnoty: hodnota může ležet o kousek výš/níž vpravo (víceřádková popiska).
    for p in pairs:
        if p.values:
            continue
        near = [o for o in orphans
                if o.page == p.chunk.page and abs(o.y - p.chunk.y) <= 10 and o.x > p.chunk.x + 100
                and not o.text[0].islower()]
        if len(near) == 1 and near[0].text in ("Ano", "Ne"):
            p.values.append(near[0].text)
            orphans.remove(near[0])
    return pairs


def _index(pairs: List[Pair]) -> Dict[str, List[str]]:
    """Klíč = popiska, opakované popisky dostanou '#2', '#3' …"""
    out: Dict[str, List[str]] = {}
    counts: Dict[str, int] = defaultdict(int)
    for p in pairs:
        counts[p.label] += 1
        key = p.label if counts[p.label] == 1 else f"{p.label}#{counts[p.label]}"
        out[key] = p.values
    return out


# ---------------------------------------------------------------- specifikace polí

# typ: int (celé Kč/dny), dec (desetinné), bool, date, range (od - do), text
# povinné = musí být v PDF; nepovinná chybějící pole mají výchozí hodnotu (0 / False / None)
EMPLOYEE_FIELDS = [
    # (klíč, popiska v PDF, typ, povinné)
    ("ik_mpsv", "OIČ (IK MPSV)", "text", True),
    ("id_ppv", "ID zaměstnání (ID PPV)", "text", True),
    ("typ_formulare", "Typ formuláře", "text", True),
    ("primarni", "Primární pracovněprávní vztah", "bool", True),
    ("druh", "Druh činnosti", "text", True),
    ("datum_nastupu", "Datum nástupu", "date", False),
    ("datum_narozeni", "Datum narození", "date", False),
    ("datum_ukonceni", "Datum ukončení", "date", False),
    ("funkcni_pozitky", "Funkční požitky dle § 6 odst. 10 ZDP", "bool", True),
    ("misto", "Místo výkonu činnosti", "text", True),
    ("typ_odlozeneho", "Typ odloženého příjmu", "text", False),
    ("apz", "Nástroj APZ (opatření)", "bool", True),
    ("docasne_prideleni", "Dočasné přidělení u uživatele", "bool", True),
    ("dny_evidencni", "Počet dní v evidenčním stavu", "int", True),
    ("prescas_hod", "Přesčasové hodiny (z odpracovaných)", "dec", False),
    ("odprac_hod", "Počet odpracovaných hodin", "dec", True),
    ("neodprac_celkem", "Celkem neodpracovaných hodin", "dec", False),
    ("neodprac_nahrada", "S náhradou či nekrácením mzdy", "dec", False),
    ("neodprac_neschop_nahrada", "Nemoc s náhradou mzdy", "dec", False),
    ("neodprac_neschop_bez", "Nemoc bez náhrady mzdy", "dec", False),
    ("neodprac_dovolena", "Dovolená", "dec", False),
    ("neodprac_osetrovne", "Ošetřovné", "dec", False),
    ("prekazky_zec", "Překážky zaměstnance", "dec", False),
    ("prekazky_zel", "Překážky zaměstnavatele", "dec", False),
    ("tydenni", "Stanovená týdenní pracovní doba", "dec", True),
    ("stanoveny_fond", "Stanovený fond pro danou profesi", "dec", True),
    ("sjednany_fond", "Sjednaný fond pracovní doby", "dec", True),
    ("riziko_hod", "Počet odpracovaných hodin#2", "dec", False),
    ("kategorizace", "Kategorizace rizika", "text", False),
    ("smeny", "Počet odprac. směn uran / ostatní", "text", False),
    ("npe", "Datum dosažení expozice NPE", "date", False),
    ("zaklad_dane", "Základ pro výpočet daně", "int", True),
    ("vydelek", "Průměrný (hrubý) hodinový výdělek", "dec", True),
    ("mzda_zuctovana", "Mzda za práci zúčtovaná", "int", True),
    ("tarif", "Tarifní mzdy", "int", True),
    ("odmeny_prav", "Prémie a odměny pravidelné", "int", True),
    ("odmeny_neprav", "Prémie a odměny nepravidelné", "int", True),
    ("priplatky_celkem", "Příplatky celkem", "int", False),
    ("priplatky_prescas", "Příplatky za práci přesčas", "int", False),
    ("priplatky_noc", "Příplatky za práci v noci", "int", False),
    ("priplatky_sobota", "Příplatky za práci soboty, neděle", "int", False),
    ("priplatky_svatek", "Příplatky za práci ve svátek", "int", False),
    ("pohotovost", "Odměny za pracovní pohotovost", "int", False),
    ("nahrady_celkem", "Náhrady mzdy zúčtované", "int", False),
    ("nahrady_dovolena", "Náhrady za dovolenou", "int", False),
    ("nahrady_svatky", "Náhrady za svátky", "int", False),
    ("nahrady_prek_zel", "Náhrady - překážky zaměstnavatele", "int", False),
    ("nahrady_prek_zec", "Náhrady - překážky zaměstnance", "int", False),
    ("nahrady_nemoc", "Náhrady za nemoc", "int", False),
    ("pojisteni", "Pojištění od - do", "range", True),
    ("eldp_kod", "Kód ELDP", "text", True),
    ("eldp_dny", "Kalendářní dny pojištění", "int", True),
    ("eldp_platnost", "Platnost kódu", "range", True),
    ("eldp_vz", "Vyměřovací základ", "int", True),
    ("odecitane_celkem", "Doby odečítané celkem", "int", False),
    ("vyloucene_celkem", "Vyloučené doby celkem", "int", False),
    ("vyloucene_nem_celkem", "Vyloučené dny celkem", "int", False),
    ("prijem_vc_nepoj", "Vykázaný příjem vč. nepojištěné činnosti", "int", True),
    ("vz_zec", "Vyměřovací základ zaměstnance", "int", True),
    ("vz_a", "z toho standardní zaměstnání", "int", True),
    ("vz_b", "z toho záchranáři", "int", False),
    ("vz_c", "z toho riziková zaměstnání", "int", False),
    ("poj_zel", "Pojistné zaměstnavatel před slevou", "int", True),
    ("poj_zec", "Pojistné zaměstnanec před slevou", "int", True),
    ("sleva_zel", "Sleva na pojistném zaměstnavatele", "bool", False),
    ("sleva_duchodce", "Sleva pracující důchodce", "bool", False),
    ("sleva_ovo", "Sleva ovocnáři, zelináři", "bool", False),
    ("zuctovano", "Zúčtovaný příjem celkem", "int", True),
    ("odmeny_nerez", "z toho odměny členů orgánů PO (daňový nerezident ČR)", "int", False),
    ("osvobozeno", "z toho osvobozené příjmy celkem", "int", False),
    ("prisp_celkem", "Příspěvek zaměstnavatele celkem", "int", False),
    ("prisp_penz_pripoj", "Příspěvek na penzijní připojištění se státním příspěvkem", "int", False),
    ("prisp_dps", "Příspěvek na doplňkové penzijní spoření", "int", False),
    ("prisp_penz_poj", "Příspěvek na penzijní pojištění", "int", False),
    ("prisp_zivot", "Příspěvek na soukromé životní pojištění", "int", False),
    ("prisp_dip", "Příspěvek na dlouhodobý investiční produkt", "int", False),
    ("prisp_pece", "Příspěvek na pojištění dlouhodobé péče", "int", False),
    ("cisty", "Čistý příjem", "int", True),
    ("srazky", "dohody o srážkách z příjmu", "bool", True),
    ("ozp", "Osoba se zdravotním postižením na chráněném trhu práce", "bool", False),
    ("zp_zel", "Pojistné za zaměstnavatele", "int", True),
    ("zp_zec", "Pojistné za zaměstnance", "int", True),
    ("prohlaseni", "Prohlášení poplatníka daně z příjmů ze závislé činnosti", "bool", True),
    ("zaklad_zalohy", "Základ pro výpočet zálohy na daň", "int", False),
    ("vypoctena", "Vypočtená záloha na daň", "int", False),
    ("sleva_poplatnik", "Základní sleva na poplatníka", "int", False),
    ("sleva_inval12", "Základní sleva na invaliditu (I. nebo II. stupeň)", "int", False),
    ("sleva_inval3", "Rozšířená sleva na invaliditu (III. stupeň)", "int", False),
    ("sleva_ztpp", "Sleva na držitele průkazu ZTP/P", "int", False),
    ("zvyh_deti", "Měsíční daňové zvýhodnění na děti", "int", False),
    ("sleva_deti", "Měsíční sleva na děti", "int", False),
    ("srazena_zaloha", "Skutečně sražená záloha na daň po slevách", "int", False),
    ("bonus", "Výše vyplaceného měsíčního daň. bonusu", "int", False),
    ("zaklad_zvl", "Základ pro výpočet daně podle zvláštní sazby daně", "int", False),
    ("srazena_zvl", "Skutečně sražená daň podle zvláštní sazby daně / měsíc", "int", False),
    ("odmena_nerez_zvl", "Odměna člena (nerezidenta) orgánu PO", "int", False),
    ("srazena_nerez", "Sražená záloha na daň z příjmu nerezidenta", "int", False),
]

# Dílčí dny ELDP – podporujeme jen nulové hodnoty (jinak je potřeba ruční podání).
ELDP_DAY_LABELS = [
    "Dny nemoci", "Dny do porodu", "Dny ošetřovného", "Dny otcovské", "Dny § 16",
    "Dny neplac. volno", "Dny náhrady za nemoc", "Dny dávky nem. poj.",
    "Dny nemoci (důchod)", "Dny do porodu (důchod)", "Dny ošetř. náleží (důchod)",
    "Dny ošetř. nenál. (důchod)", "Dny otcovské (důchod)", "Dny nepl. volno (důchod)",
    "Dny absence (důchod)",
]

HEADER_FIELDS = [
    ("typ_podani", "Typ podání", "text", True),
    ("variabilni_symbol", "Variabilní symbol", "text", True),
    ("email", "E-mail", "text", False),
    ("specificka", "Specifická právní skutečnost", "text", False),
    ("spec_datum", "Datum", "text", False),
    ("vyplatni_termin", "Výplatní termín", "text", False),
    ("zaklad_a", "Úhrn vyměřovacích základů (standardní)", "int", True),
    ("pojistne_a", "z toho pojistné za zaměstnavatele", "int", True),
    ("zaklad_b", "Úhrn vyměřovacích základů (záchranáři)", "int", True),
    ("pojistne_b", "z toho pojistné za zaměstnavatele#2", "int", True),
    ("zaklad_c", "Úhrn vyměřovacích základů (riziková zaměstnání)", "int", True),
    ("pojistne_c", "z toho pojistné za zaměstnavatele#3", "int", True),
    ("pojistne_zamestnavatele", "Pojistné za zaměstnavatele celkem", "int", True),
    ("pojistne_zamestnance", "Pojistné za zaměstnance celkem", "int", True),
    ("pojistne_celkem", "Pojistné celkem", "int", True),
    ("sleva_zel_pocet", "počet zaměstnanců", "int", True),
    ("sleva_zel_uhrn", "úhrn vyměřovacích základů zaměstnanců", "int", True),
    ("sleva_zel", "sleva na pojistném zaměstnavatele", "int", True),
    ("sleva_duch_pocet", "počet zaměstnanců#2", "int", True),
    ("sleva_duch_uhrn", "úhrn vyměřovacích základů zaměstnanců#2", "int", True),
    ("sleva_duch", "úhrn slev na pojistném zaměstnanců", "int", True),
    ("sleva_ovo_pocet", "počet zaměstnanců#3", "int", True),
    ("sleva_ovo_uhrn", "úhrn vyměřovacích základů zaměstnanců#3", "int", True),
    ("sleva_ovo", "úhrn slev na pojistném zaměstnanců#2", "int", True),
    ("uhrada", "Rozdíl mezi pojistným celkem a slevami na pojistném", "int", True),
    ("dan_zaloha_po_sleve", "Úhrn skutečně sražených záloh na dani po slevách", "int", True),
    ("dan_bonus", "Úhrn vyplacených měsíčních daňových bonusů", "int", True),
]

# Popisky, které Money tiskne na více řádků; v PDF je vidět jen jejich konec.
MULTILINE_LABELS = {"dohody o srážkách z příjmu"}

PVPOJ_KEYS = [k for k, *_ in HEADER_FIELDS[6:25]]


def _convert(kind: str, raw: Optional[str], label: str, who: str):
    if raw is None or raw == "":
        return None
    try:
        if kind == "int":
            v = num(raw)
            if v != v.to_integral_value():
                raise ValueError(f"'{raw}' není celé číslo")
            return int(v)
        if kind == "dec":
            return num(raw)
        if kind == "bool":
            return yesno(raw)
        if kind == "date":
            return date_cz(raw)
        if kind == "range":
            return date_range(raw)
        return raw
    except ValueError as e:
        raise ParseError(f"Pole '{label}'{who}: {e}")


DEFAULTS = {"int": 0, "dec": Decimal("0"), "bool": False}


def _read_fields(idx: Dict[str, List[str]], spec, who: str) -> dict:
    out = {}
    for key, label, kind, required in spec:
        if label in idx:
            values = idx[label]
            raw = values[0] if values else None
        else:
            # víceřádková popiska (jen známé případy): hledej popisku, která tímto textem končí
            match = [k for k in idx if k.endswith(label)] if label in MULTILINE_LABELS else []
            raw = idx[match[0]][0] if match and idx[match[0]] else None
            if not match and required:
                raise ParseError(f"Chybí pole '{label}'{who}. Změnil se tisk JMHZ v Money S3?")
        val = _convert(kind, raw, label, who)
        if val is None:
            if required:
                raise ParseError(f"Pole '{label}'{who} je prázdné")
            val = DEFAULTS.get(kind)
        out[key] = val
    return out


# ---------------------------------------------------------------- model

@dataclass
class Employee:
    cislo: str
    jmeno_cele: str
    vztah: str
    f: dict = field(default_factory=dict)
    eldp_dny_detail: Dict[str, int] = field(default_factory=dict)
    eldp_count: int = 1

    @property
    def ik_mpsv(self) -> str:
        return self.f["ik_mpsv"]

    @property
    def id_ppv(self) -> str:
        return self.f["id_ppv"]

    @property
    def primarni(self) -> bool:
        return self.f["primarni"]

    @property
    def druh_cinnosti(self) -> str:
        return self.f["druh"].split(" - ")[0].strip()

    @property
    def misto(self) -> Tuple[str, str, str]:
        m = re.fullmatch(r"(.+?)\s*\[(\d+)\]\s*\[([A-Z]{2})\]", self.f["misto"] or "")
        if not m:
            raise ParseError(f"Místo výkonu činnosti '{self.f['misto']}' u {self.jmeno_cele}: "
                             "očekáváno 'Obec [kód obce] [stát]'")
        return m.group(1), m.group(2), m.group(3)


@dataclass
class Report:
    mesic: int
    rok: int
    nazev: str
    ico: str
    typ_podani: str
    variabilni_symbol: str
    email: Optional[str]
    specificka_skutecnost: Optional[str]
    pvpoj: Dict[str, int]
    dan_zaloha_po_sleve: int
    dan_bonus: int
    employees: List[Employee]


# ---------------------------------------------------------------- hlavní funkce

def _row_text(row: Row) -> str:
    return " ".join(c.text for c in row)


def parse_report(rows: List[Row]) -> Report:
    if not rows or TITLE not in _row_text(rows[0]):
        raise ParseError("Soubor není tisk 'Jednotné měsíční hlášení zaměstnavatele' z Money S3")
    m = re.search(r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\s+(\d{4})",
                  _row_text(rows[0]).lower())
    if not m:
        raise ParseError("V záhlaví chybí měsíc a rok hlášení")
    mesic, rok = MONTHS[m.group(1)], int(m.group(2))

    company = rows[1] if len(rows) > 1 else []
    nazev = company[0].text if company else ""
    ico_m = re.search(r"IČ:\s*(\d+)", _row_text(company))
    ico = ico_m.group(1) if ico_m else ""

    # rozdělení na hlavičku a zaměstnance
    blocks: List[Tuple[Optional[re.Match], List[Row]]] = [(None, [])]
    for row in rows[2:]:
        em = EMPLOYEE_START.match(row[0].text)
        if em and row[0].x < 60:
            blocks.append((em, [row]))
        else:
            blocks[-1][1].append(row)

    head = _read_fields(_index(_pairs(blocks[0][1])), HEADER_FIELDS, " v souhrnné části")
    employees = []
    for em, erows in blocks[1:]:
        vztah = erows[0][-1].text if len(erows[0]) > 1 else ""
        who = f" u zaměstnance {em.group(2)}"
        idx = _index(_pairs(erows[1:]))
        emp = Employee(em.group(1), em.group(2), vztah, _read_fields(idx, EMPLOYEE_FIELDS, who))
        emp.eldp_dny_detail = {lab: _convert("int", (idx.get(lab) or [None])[0], lab, who) or 0
                               for lab in ELDP_DAY_LABELS}
        emp.eldp_count = sum(1 for k in idx if k.split("#")[0] == "Kód ELDP")
        od, do = emp.f.pop("pojisteni")
        emp.f["pojisteni_od"], emp.f["pojisteni_do"] = od, do
        od, do = emp.f.pop("eldp_platnost")
        emp.f["eldp_od"], emp.f["eldp_do"] = od, do
        employees.append(emp)
    if not employees:
        raise ParseError("V tisku nejsou žádní zaměstnanci")

    return Report(
        mesic=mesic, rok=rok, nazev=nazev, ico=ico,
        typ_podani=head["typ_podani"], variabilni_symbol=head["variabilni_symbol"],
        email=head["email"] or None, specificka_skutecnost=head["specificka"] or None,
        pvpoj={k: head[k] for k in PVPOJ_KEYS},
        dan_zaloha_po_sleve=head["dan_zaloha_po_sleve"], dan_bonus=head["dan_bonus"],
        employees=employees,
    )


def rows_from_json(data) -> List[Row]:
    """Řádky z JSON (testovací data): [[[page, x, y, text], ...], ...]."""
    return [[Chunk(int(p), float(x), float(y), str(t)) for p, x, y, t in row] for row in data]
