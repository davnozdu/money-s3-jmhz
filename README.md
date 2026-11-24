# money-s3-jmhz

Převodník **Jednotného měsíčního hlášení zaměstnavatele (JMHZ)** z tiskové sestavy
programu **Money S3** do XML souboru pro ePortál ČSSZ.

Money S3 umí JMHZ spočítat a vytisknout, ale export do XML je jen v placeném modulu.
Tento nástroj vezme PDF tisk JMHZ (vytištěný na libovolnou PDF tiskárnu, např.
*Microsoft Print to PDF*) a vytvoří z něj:

- `JMHZ_<rok>_<měsíc>.zip` – soubor k nahrání na ePortál ČSSZ
  (služba *Podání nahráním dat z účetního systému*; ePortál vyžaduje XML zabalené v ZIP),
- `JMHZ_<rok>_<měsíc>.xml` – totéž XML k nahlédnutí.

Vše běží lokálně na vašem počítači, nic se nikam neodesílá. Podání na ePortálu
odesíláte sami.

> Nezávislý projekt, není spojen se společností Seyfor/Solitea ani s ČSSZ.
> Používáte na vlastní odpovědnost – před odesláním vždy zkontrolujte rekapitulaci na ePortálu.

## Instalace

1. Nainstalujte [Python 3.9 nebo novější](https://www.python.org/downloads/)
   (ve Windows zaškrtněte *Add python.exe to PATH*).
2. Stáhněte tento repozitář (tlačítko **Code → Download ZIP**) a rozbalte.
3. V rozbalené složce spusťte:

   ```
   pip install -r requirements.txt
   ```

## Použití

1. V Money S3 vytiskněte JMHZ za daný měsíc na PDF tiskárnu.
2. Převeďte PDF:
   - **Windows:** přetáhněte PDF myší na soubor `prevest.bat`, nebo
   - **příkazová řádka:** `python jmhz.py JMHZ-112026.pdf`
3. Vedle PDF vznikne `JMHZ_2026_11.zip`. Na ePortálu ČSSZ zvolte nahrání dat z účetního
   systému a nahrajte tento ZIP.

Program na konci vypíše rekapitulaci (vyměřovací základy, pojistné, zálohy na daň),
kterou snadno porovnáte s tiskem z Money a s rekapitulací na ePortálu:

```
JMHZ Září 2026 – Vzorová firma s.r.o. (IČ 12345678)
  Variabilní symbol:                 9999999999
  Zaměstnanci:                       1
  Rekapitulace:
    Úhrn vyměřovacích základů:       7 300 Kč
    Pojistné za zaměstnavatele:      1 811 Kč
    Pojistné za zaměstnance:         519 Kč
    Pojistné celkem:                 2 330 Kč
    Pojistné k úhradě:               2 330 Kč
    Sražené zálohy na daň:           0 Kč

Hotovo. XML ověřeno proti schématu XSD 1.4.3.6 a kontrolám ČSSZ.
```

Další volby: `--out SLOŽKA` (kam uložit výstup), `--config SOUBOR` (nastavení).

## Nastavení (nepovinné)

Zkopírujte `jmhz.example.ini` jako `jmhz.ini` (vedle `jmhz.py`):

| Volba          | Význam |
|----------------|--------|
| `tydenni_doba` | Stanovená týdenní pracovní doba (§ 79 ZP), výchozí 40 h. Použije se, když tisk z Money obsahuje hodnotu vyšší než 40 h (u dohod tiskne Money 99 h). |
| `email`        | E-mail pro notifikace ČSSZ. Pokud chybí, použije se e-mail z tisku. |

## Co se kontroluje

Soubor se vytvoří **jen tehdy, když projde všemi kontrolami**. Jinak program vypíše,
co je špatně, a nevytvoří nic.

- **XSD schéma JMHZ 1.4.3.6** (oficiální schéma ČSSZ/MPSV, přiloženo ve složce `schemas/`).
- **Vybrané kontroly z Katalogu kontrol MH 1.4.2.11**, např.:
  pojistné = sazba × vyměřovací základ se zaokrouhlením nahoru (č. 8, 118, 315),
  součty pojistného (č. 4, 11, 13, 168), úhrny základů za zaměstnance (č. 7, 216),
  ELDP – počet dnů a platnost kódu v hlášeném měsíci (č. 58, 99, 100, 134),
  hodiny (č. 20, 23), daňový bonus (č. 74), jeden primární PPV na OIČ.
- **Pravidla ePortálu, na která se při ručním vyplňování naráží:** nepovinné položky
  s nulou se do XML nezapisují (např. daňový bonus nesmí být vyplněn ani nulou),
  ELDP má platnost od prvního do posledního dne měsíce.

## Omezení

Převodník zatím podporuje jen **řádné podání** a běžné situace. Pokud tisk obsahuje
něco z následujícího, program skončí chybou a podání je nutné vyplnit ručně:

- opravné nebo storno podání, specifická právní skutečnost,
- slevy na pojistném, daňové zvýhodnění na děti (tisk neobsahuje údaje o dětech),
- riziková práce, hlubinné hornictví, OZP na chráněném trhu práce, APZ, dočasné přidělení,
- vyloučené či odečítané doby v ELDP, více řádků ELDP, odložený příjem,
- druhy činnosti s jiným datovým scénářem (K–S).

Ověřeno na tiscích z Money S3 (verze 2026) pro zaměstnance na DPČ. Pokud Money změní
tiskovou sestavu, program ohlásí, které pole nenašel.

## Vývoj

```
pip install -r requirements.txt pytest
python -m pytest
```

Testy běží na syntetických (vymyšlených) datech v `tests/fixtures/`. Pokud do kořene
projektu vložíte skutečné PDF tisky, testy je použijí také (PDF jsou v `.gitignore`).

## Licence

MIT – viz [LICENSE](LICENSE).
