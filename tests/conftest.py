import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

REAL_PDFS = sorted(glob.glob(os.path.join(ROOT, "*.pdf")))


@pytest.fixture
def real_pdfs():
    """Skutečné tisky JMHZ z Money S3 v kořeni projektu (nejsou v gitu)."""
    if not REAL_PDFS:
        pytest.skip("Chybí skutečné PDF v kořeni projektu")
    return REAL_PDFS


def pdf_for(month_token):
    """Vrátí cestu ke skutečnému PDF obsahujícímu daný token v názvu, nebo skip."""
    for p in REAL_PDFS:
        if month_token in os.path.basename(p):
            return p
    pytest.skip("Chybí PDF " + month_token)
