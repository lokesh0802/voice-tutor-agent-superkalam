"""Download NCERT Class 10 Science + Maths chapter PDFs (official ncert.nic.in links).

    python scripts/download_ncert.py
"""
import concurrent.futures as cf
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "knowledge_base" / "pdfs"
BASE = "https://ncert.nic.in/textbook/pdf/{code}{n:02d}.pdf"

BOOKS = {
    "science": ("jesc1", [
        "chemical_reactions_and_equations", "acids_bases_and_salts", "metals_and_non_metals",
        "carbon_and_its_compounds", "life_processes", "control_and_coordination",
        "how_do_organisms_reproduce", "heredity", "light_reflection_and_refraction",
        "human_eye_and_colourful_world", "electricity", "magnetic_effects_of_electric_current",
        "our_environment",
    ]),
    "maths": ("jemh1", [
        "real_numbers", "polynomials", "pair_of_linear_equations", "quadratic_equations",
        "arithmetic_progressions", "triangles", "coordinate_geometry", "introduction_to_trigonometry",
        "applications_of_trigonometry", "circles", "areas_related_to_circles",
        "surface_areas_and_volumes", "statistics", "probability",
    ]),
}


def fetch(url: str, dest: Path, retries: int = 4) -> str:
    if dest.exists() and dest.stat().st_size > 50_000:
        return f"skip  {dest.name}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                dest.write_bytes(r.read())
            return f"ok    {dest.name}"
        except Exception as e:  # NCERT's server is slow/flaky -> retry
            time.sleep(2 * (attempt + 1))
            err = e
    return f"FAIL  {dest.name}: {err}"


if __name__ == "__main__":
    jobs = []
    for subject, (code, chapters) in BOOKS.items():
        (OUT / subject).mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(chapters, 1):
            jobs.append((BASE.format(code=code, n=i), OUT / subject / f"{i:02d}_{name}.pdf"))
    with cf.ThreadPoolExecutor(6) as pool:
        for msg in pool.map(lambda j: fetch(*j), jobs):
            print(msg)
