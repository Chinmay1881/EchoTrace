"""Map AudioSet label NAMES to EchoTrace categories.

Names are resolved to indices once at startup. A typo fails loudly with
"did you mean" suggestions rather than silently scoring zero forever.
"""

from __future__ import annotations

import csv
import difflib
from pathlib import Path

import numpy as np

from echotrace import config


def load_labels(path: Path = config.LABELS_FILE) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    labels = [r[2] for r in rows[1:]]
    if len(labels) != config.LABELS_COUNT:
        raise RuntimeError(f"{path}: expected {config.LABELS_COUNT} labels, found {len(labels)}")
    return labels


class CategoryMap:
    def __init__(self, labels: list[str], categories: dict[str, list[str]] | None = None):
        self.labels = labels
        cats = categories if categories is not None else config.CATEGORIES
        index = {name: i for i, name in enumerate(labels)}
        problems = []
        self.indices: dict[str, np.ndarray] = {}
        for cat, names in cats.items():
            idx = []
            for name in names:
                if name in index:
                    idx.append(index[name])
                else:
                    hint = difflib.get_close_matches(name, labels, n=3, cutoff=0.5)
                    problems.append(f"  {cat}: '{name}' not in AudioSet labels"
                                    + (f" - did you mean {hint}?" if hint else ""))
            self.indices[cat] = np.array(idx, dtype=int)
        if problems:
            raise ValueError("Unknown AudioSet label names in config.CATEGORIES:\n" + "\n".join(problems))
        self.names = list(cats)

    def scores(self, probs: np.ndarray) -> dict[str, float]:
        """Category score = max over its member labels."""
        return {cat: float(probs[idx].max()) if len(idx) else 0.0 for cat, idx in self.indices.items()}

    def best_label(self, probs: np.ndarray, cat: str) -> tuple[str, float]:
        idx = self.indices[cat]
        j = int(idx[np.argmax(probs[idx])])
        return self.labels[j], float(probs[j])


def top_k(probs: np.ndarray, labels: list[str], k: int = config.TOP_K) -> list[tuple[str, float]]:
    order = np.argsort(probs)[::-1][:k]
    return [(labels[i], float(probs[i])) for i in order]
