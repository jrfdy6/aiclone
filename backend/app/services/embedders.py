from functools import lru_cache
from typing import Iterable, List

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


VECTOR_DIM = 1024


@lru_cache
def _get_vectorizer() -> HashingVectorizer:
    return HashingVectorizer(
        n_features=VECTOR_DIM,
        alternate_sign=False,
        norm="l2",
        stop_words="english",
    )


def embed_text(text: str) -> List[float]:
    """Return a deterministic embedding for a single piece of text."""
    vectorizer = _get_vectorizer()
    sparse = vectorizer.transform([text])
    dense = sparse.toarray()[0]
    return dense.astype(np.float32).tolist()


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    vectorizer = _get_vectorizer()
    sparse = vectorizer.transform(list(texts))
    dense = sparse.toarray().astype(np.float32)
    return dense.tolist()
