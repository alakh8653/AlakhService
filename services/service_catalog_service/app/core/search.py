import math
import re
from collections import defaultdict
from typing import Optional


class TFIDFIndex:
    """TF-IDF based full-text search index."""

    def __init__(self):
        self._documents: dict[str, str] = {}
        self._tf: dict[str, dict[str, float]] = {}
        self._df: dict[str, int] = defaultdict(int)
        self._idf: dict[str, float] = {}

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-z]{2,}\b", text.lower())

    def add_document(self, doc_id: str, text: str) -> None:
        # Re-adding an id replaces it, so an edited listing does not keep matching its old text.
        self.remove_document(doc_id)
        self._documents[doc_id] = text
        tokens = self._tokenize(text)
        if tokens:
            freq: dict[str, int] = defaultdict(int)
            for t in tokens:
                freq[t] += 1
            self._tf[doc_id] = {t: c / len(tokens) for t, c in freq.items()}
            for term in freq:
                self._df[term] += 1
        self._compute_idf()

    def _compute_idf(self) -> None:
        N = max(len(self._documents), 1)
        self._idf = {t: math.log((N + 1) / (df + 1)) + 1.0 for t, df in self._df.items()}

    def search(self, query: str, top_k: Optional[int] = 10) -> list[tuple[str, float]]:
        """Documents containing at least one query term, best score first (all of them if top_k is None)."""
        tokens = self._tokenize(query)
        if not tokens:
            return []
        scores: dict[str, float] = defaultdict(float)
        for t in tokens:
            if t not in self._idf:
                continue
            idf = self._idf[t]
            for doc_id, tf_dict in self._tf.items():
                tf = tf_dict.get(t, 0.0)
                if tf > 0:
                    scores[doc_id] += tf * idf
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return ranked if top_k is None else ranked[:top_k]

    def remove_document(self, doc_id: str) -> None:
        if doc_id not in self._documents:
            return
        del self._documents[doc_id]
        for term in self._tf.pop(doc_id, {}):
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]
        self._compute_idf()

    def clear(self) -> None:
        self._documents.clear()
        self._tf.clear()
        self._df.clear()
        self._idf = {}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute edit distance between two strings."""
    m, n = len(s1), len(s2)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


class BKTree:
    """BK-Tree for efficient fuzzy string matching using Levenshtein distance."""

    def __init__(self):
        self._root: Optional[str] = None
        self._tree: dict[str, dict] = {}

    def add(self, word: str) -> None:
        if not self._tree:
            self._tree[word] = {}
            self._root = word
            return
        current = self._root
        while True:
            d = levenshtein_distance(word, current)
            if d == 0:
                return  # duplicate
            children = self._tree[current]
            if d not in children:
                children[d] = word
                self._tree[word] = {}
                break
            current = children[d]

    def search(self, query: str, max_distance: int = 2) -> list[tuple[str, int]]:
        if not self._tree:
            return []
        results = []
        candidates = [self._root]
        while candidates:
            current = candidates.pop()
            d = levenshtein_distance(query, current)
            if d <= max_distance:
                results.append((current, d))
            lower, upper = d - max_distance, d + max_distance
            for dist, child in self._tree[current].items():
                if lower <= dist <= upper:
                    candidates.append(child)
        return sorted(results, key=lambda x: x[1])
