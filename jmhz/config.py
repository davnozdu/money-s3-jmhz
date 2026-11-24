"""Nastavení převodníku (soubor jmhz.ini)."""
import configparser
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Config:
    # Stanovená týdenní pracovní doba (§ 79 ZP). Použije se, když tisk z Money obsahuje
    # nesmyslnou hodnotu (> 40 h).
    tydenni_doba: Decimal = Decimal("40")
    # E-mail pro notifikace ČSSZ; pokud není vyplněn, použije se e-mail z tisku JMHZ.
    email: Optional[str] = None


def load_config(path: Optional[str]) -> Config:
    cfg = Config()
    if not path:
        return cfg
    parser = configparser.ConfigParser()
    with open(path, encoding="utf-8") as fh:
        parser.read_file(fh)
    sec = parser["jmhz"] if parser.has_section("jmhz") else {}
    if sec.get("tydenni_doba"):
        cfg.tydenni_doba = Decimal(sec["tydenni_doba"].strip().replace(",", "."))
    if sec.get("email"):
        cfg.email = sec["email"].strip()
    return cfg
