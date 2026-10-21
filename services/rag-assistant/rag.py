"""Assistant RAG local pour les opérateurs — Ollama + LangChain + Chroma.

Rôle : aider un opérateur à comprendre l'incident ou retrouver une procédure, en
cherchant dans les documents de l'équipe (dossier /corpus) puis en faisant répondre un
modèle local (<= 8 Mds de paramètres). LECTURE SEULE : il n'a aucun privilège système et
n'est PAS le moteur de remédiation (séparation voulue par le sujet).

L'index est construit à la première question (lazy) pour ne pas dépendre d'Ollama au boot.
"""
import os
import glob
import threading
from fastapi import FastAPI
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")          # génération (chat)
# Modèle DÉDIÉ aux embeddings : un modèle de chat n'expose pas les embeddings dans Ollama
# (erreur 501). nomic-embed-text est conçu pour ça, léger et local. -> faire: ollama pull nomic-embed-text
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CORPUS = os.environ.get("CORPUS_DIR", "/corpus")

app = FastAPI(title="Assistant RAG — RESILIENCE-ALPHA")
_store = None
_lock = threading.Lock()


def build_store():
    """Charge les .md du corpus, découpe, vectorise (embeddings Ollama) dans Chroma."""
    docs = []
    for path in glob.glob(f"{CORPUS}/**/*.md", recursive=True):
        with open(path, encoding="utf-8") as f:
            docs.append(f.read())
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.create_documents(docs) if docs else []
    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
    return Chroma.from_documents(chunks, embeddings)


def get_store():
    global _store
    with _lock:
        if _store is None:
            _store = build_store()
    return _store


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.get("/ask")
def ask(q: str):
    store = get_store()
    hits = store.similarity_search(q, k=6)   # 6 passages : fiabilise la remontée du bon extrait
    context = "\n\n".join(h.page_content for h in hits)
    prompt = (
        "Tu es un assistant pour un opérateur. Réponds en français, en t'appuyant "
        "UNIQUEMENT sur le contexte ci-dessous. Si l'info manque, dis-le.\n\n"
        f"Contexte :\n{context}\n\nQuestion : {q}\nRéponse :"
    )
    llm = OllamaLLM(model=MODEL, base_url=OLLAMA_URL)
    answer = llm.invoke(prompt)
    return {"question": q, "answer": answer, "sources": len(hits)}