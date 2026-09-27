"""RAG tests.  Run: pytest -q -s   (retrieval eval needs OPENAI_API_KEY + `python scripts/ingest.py`)"""
import os

import pytest

from tutor.rag import chunk_text, kb

# (student query, expected chapter keyword) — English, Hinglish and Hindi, like real callers
EVAL = [
    ("what is photosynthesis", "life processes"),
    ("photosynthesis kaise hota hai", "life processes"),
    ("प्रकाश संश्लेषण क्या है", "life processes"),
    ("how do we breathe, respiration in humans", "life processes"),
    ("reflex action kya hai", "control and coordination"),
    ("what does ohm's law say", "electricity"),
    ("refraction of light through glass slab", "light"),
    ("myopia aur hypermetropia", "human eye"),
    ("why is the sky blue", "human eye"),
    ("Mendel pea plant experiment", "heredity"),
    ("ozone layer depletion", "our environment"),
    ("neutralisation reaction acid and base", "acids"),
    ("rusting of iron corrosion", "chemical reactions"),
    ("right hand thumb rule magnetic field", "magnetic"),
    ("quadratic formula discriminant", "quadratic"),
    ("nth term of an AP", "arithmetic"),
    ("Pythagoras theorem similar triangles", "triangles"),
    ("distance formula between two points", "coordinate"),
    ("sin cos tan values", "trigonometry"),
    ("probability of getting a head on a coin", "probability"),
    ("mean median mode of grouped data", "statistics"),
    ("tangent to a circle", "circles"),
    ("HCF LCM prime factorisation", "real numbers"),
    ("volume of a cone", "surface areas"),
]


def test_chunker_respects_size_and_overlap():
    text = " ".join(f"Sentence number {i} explains a concept." for i in range(200))
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 5 and all(len(c) < 400 for c in chunks)


@pytest.fixture(scope="module")
def loaded_kb():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    if not kb.load().docs:
        pytest.skip("Index empty - run: python scripts/ingest.py")
    return kb


def test_subject_filter(loaded_kb):
    assert all(h["subject"] == "maths" for h in loaded_kb.search("area", subject="maths"))


def test_retrieval_hit_rate(loaded_kb):
    hits = 0
    for q, chapter in EVAL:
        got = [h["chapter"] for h in loaded_kb.search(q, k=3)]
        ok = any(chapter in c for c in got)
        hits += ok
        print(f"{'✅' if ok else '❌'} {q:45s} -> {got[0]}")
    rate = hits / len(EVAL)
    print(f"\nHit@3 = {rate:.0%}  ({hits}/{len(EVAL)})")
    assert rate >= 0.85
