"""Kontrola XML proti oficiálnímu XSD schématu JMHZ."""
import os
from functools import lru_cache
from typing import List

from lxml import etree

SCHEMA_VERSION = "1.4.3.6"
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "schemas", SCHEMA_VERSION)


@lru_cache(maxsize=1)
def _schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(os.path.join(SCHEMA_DIR, "jmhzPodani.xsd")))


def validate_xsd(tree) -> List[str]:
    """Vrátí seznam chyb (prázdný = platné)."""
    schema = _schema()
    if schema.validate(tree):
        return []
    return [f"řádek {e.line}: {e.message}" for e in schema.error_log]
