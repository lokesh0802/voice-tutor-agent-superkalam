"""Build the vector index:  python scripts/ingest.py   then try:  python scripts/ingest.py "photosynthesis" """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor.rag import kb  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1:  # quick query mode (nice to show in the Loom video)
        for r in kb.search(" ".join(sys.argv[1:])):
            print(f"\n[{r['subject']} | {r['chapter']} | p{r['page']} | rrf={r['score']}]\n{r['text'][:300]}...")
    else:
        kb.ingest()
        print(f"Indexed {len(kb.docs)} chunks")
