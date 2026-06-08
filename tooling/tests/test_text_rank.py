"""Unit tests for text_rank (BM25) and embedding_index."""
from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from text_rank import BM25Ranker, bm25_from_files, tokenize
from embedding_index import EmbeddingIndex, cosine_similarity


class TokenizeTests(unittest.TestCase):
    def test_splits_on_non_alphanumeric(self) -> None:
        self.assertEqual(tokenize("hello world"), ["hello", "world"])

    def test_dedup_preserves_order(self) -> None:
        self.assertEqual(tokenize("a b a b a"), ["a", "b"])

    def test_lowercases(self) -> None:
        self.assertEqual(tokenize("Login BUTTON"), ["login", "button"])

    def test_cjk_expands_to_bigrams(self) -> None:
        # "登录按钮" → bigrams 登录/录按/按钮 + unigrams, so "登录" matches.
        tokens = tokenize("登录按钮")
        self.assertIn("登录", tokens)
        self.assertIn("按钮", tokens)
        self.assertIn("录按", tokens)  # overlapping bigram

    def test_single_cjk_char(self) -> None:
        self.assertEqual(tokenize("车"), ["车"])

    def test_mixed_ascii_cjk(self) -> None:
        tokens = tokenize("cart 购物车 item")
        self.assertIn("cart", tokens)
        self.assertIn("购物", tokens)  # bigram of 购物车
        self.assertIn("item", tokens)


class BM25RankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.docs = [
            "apple banana cherry",                # doc 0
            "apple apple date",                   # doc 1 — "apple" appears twice
            "banana elderberry fig grape honey",  # doc 2 — long doc
            "cherry",                             # doc 3 — very short
        ]
        self.ranker = BM25Ranker(self.docs)

    def test_requires_at_least_one_doc(self) -> None:
        with self.assertRaises(ValueError):
            BM25Ranker([])

    def test_exact_term_scores_higher_in_doc_with_higher_tf(self) -> None:
        # "apple" appears once in doc 0, twice in doc 1.
        s0 = self.ranker.score("apple", 0)
        s1 = self.ranker.score("apple", 1)
        self.assertGreater(s1, s0)

    def test_term_not_in_corpus_scores_zero(self) -> None:
        self.assertEqual(self.ranker.score("zzzmissing", 0), 0.0)

    def test_long_doc_not_penalized(self) -> None:
        # "banana" appears once in doc 0 (3 tokens) and once in doc 2 (5 tokens).
        # BM25's length normalization means doc 2 should still get a reasonable
        # score, not near-zero.
        s_short = self.ranker.score("banana", 0)
        s_long = self.ranker.score("banana", 2)
        # Both should be positive; the ratio should not be extreme.
        self.assertGreater(s_short, 0)
        self.assertGreater(s_long, 0)

    def test_empty_query_returns_zero(self) -> None:
        self.assertEqual(self.ranker.score("", 0), 0.0)
        self.assertEqual(self.ranker.score("   ", 0), 0.0)

    def test_top_k_returns_ranked_results(self) -> None:
        top = self.ranker.top_k("cherry", k=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0][0], 3)  # doc 3 is pure "cherry"
        self.assertGreater(top[0][1], top[1][1])

    def test_scores_returns_all_documents(self) -> None:
        scores = self.ranker.scores("apple")
        self.assertEqual(len(scores), 4)
        self.assertEqual(scores[2], 0.0)  # doc 2 has no "apple"

    def test_min_score_filters(self) -> None:
        top = self.ranker.top_k("cherry", k=5, min_score=0.01)
        # Only docs containing "cherry" should appear.
        indices = {i for i, _ in top}
        self.assertIn(0, indices)  # doc 0 has "cherry"
        self.assertIn(3, indices)  # doc 3 has "cherry"
        self.assertNotIn(1, indices)  # doc 1 no "cherry"

    def test_out_of_range_index_scores_zero(self) -> None:
        self.assertEqual(self.ranker.score("apple", -1), 0.0)
        self.assertEqual(self.ranker.score("apple", 999), 0.0)


class CjkMatchingTests(unittest.TestCase):
    """The whole point of CJK bigrams: cross-phrase Chinese matching."""

    def test_query_matches_substring_of_chinese_phrase(self) -> None:
        docs = [
            "购物车起送价限制问题，去结算按钮高亮",  # doc 0 — about cart minimum
            "登录页面账户信息写入逻辑",              # doc 1 — about login
        ]
        ranker = BM25Ranker(docs)
        # Query "起送价" should rank doc 0 first even though the doc embeds it
        # in a longer phrase with no spaces.
        top = ranker.top_k("起送价", k=2)
        self.assertEqual(top[0][0], 0)
        self.assertGreater(top[0][1], 0)

    def test_login_query_matches_login_doc(self) -> None:
        docs = [
            "购物车结算流程优化",
            "登录账户信息处理",
        ]
        ranker = BM25Ranker(docs)
        top = ranker.top_k("登录", k=1)
        self.assertEqual(top[0][0], 1)


class BM25FromFilesTests(unittest.TestCase):
    def test_builds_ranker_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.md"
            b = Path(tmp) / "b.md"
            a.write_text("hello world", encoding="utf-8")
            b.write_text("hello again", encoding="utf-8")
            ranker = bm25_from_files([a, b])
            self.assertGreater(ranker.score("hello", 0), 0)
            self.assertGreater(ranker.score("hello", 1), 0)


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 2.0], [1.0, 2.0]), 1.0)

    def test_orthogonal_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_zero_vector(self) -> None:
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 2.0]), 0.0)
        self.assertEqual(cosine_similarity([1.0, 2.0], [0.0, 0.0]), 0.0)

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1.0], [1.0, 2.0])


class EmbeddingIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Create two little markdown files.
        (self.root / "patterns").mkdir(parents=True)
        (self.root / "patterns" / "a.md").write_text("# login button pattern", encoding="utf-8")
        (self.root / "patterns" / "b.md").write_text("# cart checkout pattern", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_and_search(self) -> None:
        idx = EmbeddingIndex()
        idx.build_index(
            paths=[self.root / "patterns" / "a.md", self.root / "patterns" / "b.md"],
            embed_fn=lambda text: [1.0, 0.0] if "login" in text else [0.0, 1.0],
        )
        self.assertEqual(len(idx), 2)

        hits = idx.search([1.0, 0.0], top_k=1)
        self.assertEqual(len(hits), 1)
        self.assertIn("a.md", hits[0][0])

    def test_empty_index_search_returns_empty(self) -> None:
        idx = EmbeddingIndex()
        self.assertEqual(idx.search([0.5, 0.5]), [])

    def test_save_and_load_roundtrip(self) -> None:
        idx = EmbeddingIndex()
        idx._vectors = {"/x/a.md": [0.1, 0.2, 0.3]}
        cache_path = self.root / ".embedding_cache.json"
        idx.save(cache_path)

        loaded = EmbeddingIndex.load(cache_path)
        self.assertEqual(len(loaded), 1)
        self.assertAlmostEqual(loaded._vectors["/x/a.md"][0], 0.1)

    def test_load_missing_file_returns_empty(self) -> None:
        idx = EmbeddingIndex.load(self.root / "nonexistent.json")
        self.assertEqual(len(idx), 0)
        self.assertFalse(idx)

    def test_load_corrupt_file_returns_empty(self) -> None:
        bad = self.root / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        idx = EmbeddingIndex.load(bad)
        self.assertEqual(len(idx), 0)

    def test_falsy_empty_index(self) -> None:
        idx = EmbeddingIndex()
        self.assertFalse(idx)
        idx._vectors = {"/a": [1.0]}
        self.assertTrue(idx)


if __name__ == "__main__":
    unittest.main()
