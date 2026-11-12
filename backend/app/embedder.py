"""
The embedding model: turns text into a vector (a list of numbers) that
represents its meaning.

We use BAAI/bge-small-en-v1.5, a free open-source model that runs on your own
computer through the `fastembed` library (no API key, no cost). It gives
384 numbers per text. Bigger models give around 1,024; the idea is the same.

The same-model rule from lesson 02: passages and questions MUST go through this
same model, or their numbers can't be compared.
"""

import hashlib
import os

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_VERSION = "fastembed-0.7"  # the library build that produced the numbers


class Embedder:
    def __init__(self) -> None:
        from fastembed import TextEmbedding  # imported here so tests can skip it

        # The first run downloads the model (about 130 MB) and caches it.
        self.model = TextEmbedding(MODEL_NAME)
        self.name = MODEL_NAME
        # Stored on every chunk row: a new model or version means re-embedding everything.
        self.version = MODEL_VERSION

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        # One row per passage, one column per dimension.
        return np.array(list(self.model.passage_embed(texts)))

    def embed_query(self, text: str) -> np.ndarray:
        # bge models were trained to treat questions slightly differently from
        # passages, so questions get their own method. Same model, same space.
        return np.array(list(self.model.query_embed(text))[0])


class FakeEmbedder:
    """
    FOR TESTS ONLY. Not a real embedding model: it just counts words, so it
    behaves like keyword search. It lets us test the plumbing on a computer
    that can't download the real model. Switch it on with RAG_FAKE_EMBEDDER=1.
    """

    DIMS = 384

    def __init__(self) -> None:
        self.name = "fake-word-counter (tests only)"
        self.version = "1"

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.DIMS)
        for word in text.lower().split():
            word = word.strip(".,?!'\"")
            if len(word) > 3:
                # A stable hash, so the same word lands in the same slot in every process.
                slot = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16) % self.DIMS
                v[slot] += 1.0
        return v + 1e-6

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vec(t) for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


def load_embedder():
    if os.environ.get("RAG_FAKE_EMBEDDER") == "1":
        return FakeEmbedder()
    return Embedder()
