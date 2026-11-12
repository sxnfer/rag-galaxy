import numpy as np

from pipeline.chunk.search import cosine_search


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def test_ranks_by_cosine_and_returns_k():
    m = np.array([unit([1, 0, 0]), unit([1, 1, 0]), unit([0, 1, 0]), unit([-1, 0, 0])])
    out = cosine_search(unit([1, 0.2, 0]), m, 2)
    assert [i for i, _ in out] == [0, 1]
    assert abs(out[0][1] - float(unit([1, 0.2, 0]) @ m[0])) < 1e-9


def test_agrees_with_brute_force_on_random_data():
    rng = np.random.default_rng(0)
    m = rng.normal(size=(500, 384)); m /= np.linalg.norm(m, axis=1, keepdims=True)
    q = unit(rng.normal(size=384))
    out = cosine_search(q, m, 5)
    brute = sorted(range(500), key=lambda i: -(m[i] @ q))[:5]
    assert [i for i, _ in out] == brute
