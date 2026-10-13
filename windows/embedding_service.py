"""CPU embedding endpoint compatible with Stage-2B's existing /embed contract."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "embedding"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

app = FastAPI(title="Docling Stage-2B Local Embeddings")
_lock = Lock()
_model = None


class EmbedRequest(BaseModel):
    inputs: list[str] = Field(min_length=1, max_length=128)


def get_model():
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            if not (MODEL / "modules.json").is_file():
                raise RuntimeError("Bundled embedding model is missing")
            _model = SentenceTransformer(str(MODEL), device="cpu")
        return _model


@app.on_event("startup")
def preload() -> None:
    # Fail startup rather than claiming that offline embedding is ready.
    get_model()


@app.get("/health")
def health():
    return {"ok": _model is not None, "model": "BAAI/bge-small-en-v1.5"}


@app.post("/embed")
async def embed(request: EmbedRequest):
    def compute():
        with _lock:
            values = get_model_unlocked().encode(
                request.inputs, batch_size=16, normalize_embeddings=True,
                convert_to_numpy=True, show_progress_bar=False,
            )
        return values.tolist()
    return await asyncio.to_thread(compute)


def get_model_unlocked():
    # Caller already holds _lock. Avoid recursively acquiring threading.Lock.
    if _model is None:
        raise RuntimeError("Embedding model not initialized")
    return _model
