import os
import json
import numpy as np
import faiss
from typing import List, Dict
from openai import OpenAI

INDEX_DIR = ".faiss"

def _read_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def _chunk_text(text: str, chunk_chars: int = 900, overlap: int = 120) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+chunk_chars])
        i += (chunk_chars - overlap)
    return chunks

class JobRAG:
    def __init__(self, job_file: str):
        self.job_file = job_file
        self.index = None
        self.texts: List[str] = []
        self.meta: List[Dict] = []

    def _paths(self):
        base = os.path.basename(self.job_file).replace(".jsonl", "")
        os.makedirs(INDEX_DIR, exist_ok=True)
        return (
            os.path.join(INDEX_DIR, f"{base}.faiss"),
            os.path.join(INDEX_DIR, f"{base}.pkl.json")
        )

    def build_or_load(self):
        index_path, meta_path = self._paths()
        if os.path.exists(index_path) and os.path.exists(meta_path):
            self.index = faiss.read_index(index_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                blob = json.load(f)
            self.texts = blob["texts"]
            self.meta = blob["meta"]
            return

        # Build new index
        jobs = _read_jsonl(self.job_file)
        all_chunks = []
        all_meta = []
        for j in jobs:
            for c in _chunk_text(j.get("text", "")):
                all_chunks.append(c)
                all_meta.append({"source": j.get("source", "unknown"), "role": j.get("role", "")})

        # Embed using OpenAI embeddings
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY required to build FAISS index. Set it and rerun.")

        vecs = []
        batch_size = 64
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i+batch_size]
            resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
            vecs.extend([x.embedding for x in resp.data])

        X = np.array(vecs, dtype="float32")
        faiss.normalize_L2(X)

        index = faiss.IndexFlatIP(X.shape[1])
        index.add(X)

        self.index = index
        self.texts = all_chunks
        self.meta = all_meta

        faiss.write_index(index, index_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"texts": self.texts, "meta": self.meta}, f)

    def retrieve(self, query: str, k: int = 10) -> List[Dict]:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        resp = client.embeddings.create(model="text-embedding-3-small", input=[query])
        q = np.array([resp.data[0].embedding], dtype="float32")
        faiss.normalize_L2(q)

        scores, idx = self.index.search(q, k)
        out = []
        for i, s in zip(idx[0], scores[0]):
            if i == -1:
                continue
            out.append({"text": self.texts[i], "score": float(s), "meta": self.meta[i]})
        return out
