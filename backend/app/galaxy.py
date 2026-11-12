"""
The galaxy picture for the real documents: every chunk of the active run as a
star, squeezed from 384 numbers to 3 with PCA. Drawing only; search always
uses the full embedding (lesson 02).
"""

import numpy as np

GALAXY_RADIUS = 3.0


class Galaxy:
    def __init__(self, rows: list[tuple]) -> None:
        # rows: (chunk_id, embedding, breadcrumb, doc_type, project_id, page_start, page_end, doc_sha256, meta)
        # meta is None for chunks cut from PDFs; cards from a table carry their car and class there.
        self.rows = rows
        if len(rows) < 4:
            self.positions = np.zeros((len(rows), 3))
            self.mean, self.directions, self.scale = None, None, 1.0
            return
        vectors = np.array([r[1] for r in rows])
        self.mean = vectors.mean(axis=0)
        _, _, d = np.linalg.svd(vectors - self.mean, full_matrices=False)
        self.directions = d[:3]
        raw = (vectors - self.mean) @ self.directions.T
        self.scale = GALAXY_RADIUS / np.abs(raw).max()
        self.positions = raw * self.scale

    def project(self, v: np.ndarray) -> list[float]:
        if self.directions is None:
            return [0.0, 0.0, 0.0]
        return [round(float(x), 3) for x in ((v - self.mean) @ self.directions.T) * self.scale]

    def stars(self) -> list[dict]:
        out = []
        for r, p in zip(self.rows, self.positions, strict=True):
            star = {"id": r[0], "breadcrumb": r[2], "doc_type": r[3], "project_id": r[4],
                    "pages": [r[5], r[6]], "position": [round(float(x), 3) for x in p]}
            if r[8]:
                star["item_class"] = r[8]["class"]  # the site tints the stars by class
            out.append(star)
        return out
