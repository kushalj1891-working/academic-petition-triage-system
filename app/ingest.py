"""Rebuild local vector index. Run: python -m app.ingest"""
from app.retrieval import corpus

if __name__=="__main__":
    c=corpus()
    print(f"Indexed {len(c.docs)} clauses; mode={'FAISS' if c.index is not None else 'lexical fallback'}")
