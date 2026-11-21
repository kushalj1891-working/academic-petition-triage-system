"""Reproducible local retrieval: sentence-transformers + FAISS when installed; lexical fallback for offline startup."""
import json, os, re, hashlib
import time
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
CORPUS=ROOT/"data"/"corpus.json"
INDEX=ROOT/"data"/"faiss_index"
INDEX_HASH=ROOT/"data"/"faiss_index.sha256"

def load_docs(): return json.loads(CORPUS.read_text(encoding="utf-8"))
def words(s): return set(re.findall(r"[a-z0-9]+",s.lower()))

class Corpus:
    def __init__(self):
        self.docs=load_docs(); self.encoder=None; self.index=None; self.vectorstore=None; self.vector_failures=0; self.vector_open_until=0.0
        try:
            from langchain_core.embeddings import Embeddings
            from langchain_community.vectorstores import FAISS
            from sentence_transformers import SentenceTransformer
            model_name=os.getenv("EMBEDDING_MODEL","").strip()
            if not model_name: raise RuntimeError("EMBEDDING_MODEL is not configured; lexical fallback is active")
            encoder=SentenceTransformer(model_name)
            class LocalEmbeddings(Embeddings):
                def embed_documents(self,texts): return encoder.encode(texts,normalize_embeddings=True).tolist()
                def embed_query(self,text): return encoder.encode([text],normalize_embeddings=True)[0].tolist()
            self.encoder=LocalEmbeddings()
            digest=hashlib.sha256(CORPUS.read_bytes()).hexdigest()
            if INDEX.exists() and INDEX_HASH.exists() and INDEX_HASH.read_text().strip()==digest:
                self.vectorstore=FAISS.load_local(str(INDEX),self.encoder,allow_dangerous_deserialization=True)
            else:
                self.vectorstore=FAISS.from_texts([d['text'] for d in self.docs],self.encoder,metadatas=[{"doc_index":i} for i in range(len(self.docs))])
                self.vectorstore.save_local(str(INDEX)); INDEX_HASH.write_text(digest)
            self.index=self.vectorstore
        except Exception: pass

    def search(self, query, k=5, category=None):
        return self._search_cached(query,k,category)

    @lru_cache(maxsize=256)
    def _search_cached(self, query, k=5, category=None):
        docs=[d for d in self.docs if not category or d['category']==category]
        if self.vectorstore is not None and time.monotonic()>=self.vector_open_until:
            try:
                hits=self.vectorstore.similarity_search_with_score(query,k=len(self.docs)); self.vector_failures=0
                ranked=[]
                for doc,distance in hits:
                    i=int(doc.metadata['doc_index']); record=self.docs[i]
                    if category and record['category']!=category: continue
                    ranked.append({**record,"score":1/(1+float(distance))})
                return ranked[:k]
            except Exception:
                self.vector_failures+=1
                if self.vector_failures>=2: self.vector_open_until=time.monotonic()+30
        q=words(query)
        ranked=sorted(((len(q & words(d['text']+" "+d['title']))/(len(q|words(d['text']+" "+d['title'])) or 1),d) for d in docs),key=lambda x:x[0],reverse=True)
        return [{**d,"score":score} for score,d in ranked[:k] if score>0]

@lru_cache(maxsize=1)
def corpus(): return Corpus()

def tool_search(query, category=None): return corpus().search(query,category=category)
def tool_clause(clause_id): return [d for d in load_docs() if d['clause_id'].lower()==clause_id.lower()]
def tool_field(field, petition): return petition.get(field)
