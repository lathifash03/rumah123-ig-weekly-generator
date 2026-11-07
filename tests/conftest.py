import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.models import Fact, Item, VerifiedItem


@pytest.fixture
def facts():
    return [
        Fact(
            claim="Harga rumah naik 8,43 persen pada kuartal III",
            quote="harga rumah naik 8,43 persen pada kuartal III 2026",
        ),
        Fact(
            claim="Suku bunga acuan BI ditahan di 5,25 persen",
            quote="Bank Indonesia menahan suku bunga acuan di 5,25 persen",
        ),
    ]


@pytest.fixture
def item():
    return Item(
        title="Survei BI: Harga Rumah Naik Tipis",
        url="https://example.co.id/ekonomi/harga-rumah-naik",
        published="2026-11-06T02:00:00+00:00",
        source="CNN Indonesia Ekonomi",
        source_display="CNN Indonesia",
        summary="Survei Bank Indonesia menunjukkan harga rumah naik tipis.",
    )


@pytest.fixture
def vitem(item, facts):
    return VerifiedItem(item=item, facts=facts)


# A caption that passes every rule. Used as the "good" fixture everywhere.
PASSING_CAPTION = """Pernah merasa harga rumah bergerak lebih cepat dari tabungan kamu?

Menurut CNN Indonesia, harga rumah naik 8,43 persen pada kuartal III.

Bank Indonesia menahan suku bunga acuan di 5,25 persen.

Artinya biaya pinjaman belum berubah, jadi kamu punya waktu untuk berhitung.

Di Rumah123 kamu bisa lihat-lihat dulu tanpa perlu buru.

Menurut kamu, apa langkah pertama yang paling masuk akal?

#Rumah123 #KPR"""


@pytest.fixture
def passing_caption():
    return PASSING_CAPTION


class StubLLM:
    """Scripted stand-in for the OpenAI client. No network, no API key."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.model = "stub-model"

    def json(self, system, user, schema):
        self.calls.append({"system": system[:40], "user": user, "schema": schema["name"]})
        if not self.responses:
            raise AssertionError("StubLLM ran out of scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


@pytest.fixture
def stub_llm():
    return StubLLM
