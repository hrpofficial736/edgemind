"""Local text -> vector. Runs on CPU, no network once the model is cached."""
import hashlib
import math
import os
import re

from config import DIM, MODEL_DIR, MODEL_NAME

_model = None


def _fake(text: str) -> list[float]:
    # Test-only hook (FAKE_EMBED=1): hashed bag-of-words, so tests need no model.
    vec = [0.0] * DIM
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed(text: str) -> list[float]:
    if os.getenv("FAKE_EMBED") == "1":
        return _fake(text)
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        MODEL_DIR.mkdir(exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_DIR))
    return next(iter(_model.embed([text]))).tolist()
