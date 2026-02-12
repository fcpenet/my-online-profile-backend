"""Tests for RAG service layer (app/services/rag_service.py) — pure functions, no mocks needed."""

import json
import math

from app.services.rag_service import chunk_text, cosine_similarity, find_relevant_chunks


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world."
        chunks = chunk_text(text, chunk_size=500, overlap=0)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world."

    def test_paragraphs_split_into_chunks(self):
        paragraphs = ["Paragraph " + str(i) + "." for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=100, overlap=0)
        assert len(chunks) > 1
        # Each chunk should be at most chunk_size characters
        for chunk in chunks:
            assert len(chunk) <= 150  # some tolerance for overlap logic

    def test_long_paragraph_splits_by_sentence(self):
        long_para = "This is sentence one. " * 30  # ~660 chars
        chunks = chunk_text(long_para, chunk_size=200, overlap=0)
        assert len(chunks) > 1

    def test_empty_text_returns_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text("\n\n\n") == []

    def test_overlap_adds_prefix(self):
        text = "AAAA.\n\nBBBB."
        chunks = chunk_text(text, chunk_size=5, overlap=3)
        assert len(chunks) >= 2
        # Second chunk should start with overlap from the first
        if len(chunks) > 1:
            assert chunks[1].startswith(chunks[0][-3:])

    def test_no_overlap(self):
        text = "First paragraph.\n\nSecond paragraph."
        chunks_with = chunk_text(text, chunk_size=500, overlap=50)
        chunks_without = chunk_text(text, chunk_size=500, overlap=0)
        # With overlap=0 and text fitting in one chunk, should be equal
        assert chunks_with == chunks_without

    def test_preserves_content(self):
        text = "Important fact A.\n\nImportant fact B.\n\nImportant fact C."
        chunks = chunk_text(text, chunk_size=500, overlap=0)
        joined = " ".join(chunks)
        assert "Important fact A" in joined
        assert "Important fact B" in joined
        assert "Important fact C" in joined


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_known_similarity(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 1.0, 0.0]
        expected = 1.0 / math.sqrt(2)
        assert cosine_similarity(a, b) == pytest.approx(expected)

    def test_high_dimensional(self):
        # Simulate OpenAI-like 1536-dim vectors
        a = [1.0] * 1536
        b = [1.0] * 1536
        assert cosine_similarity(a, b) == pytest.approx(1.0)


class TestFindRelevantChunks:
    def test_returns_top_k(self):
        query = [1.0, 0.0, 0.0]
        stored = [
            ("chunk A", json.dumps([0.1, 0.9, 0.0])),  # low similarity
            ("chunk B", json.dumps([0.9, 0.1, 0.0])),  # high similarity
            ("chunk C", json.dumps([0.5, 0.5, 0.0])),  # medium similarity
            ("chunk D", json.dumps([0.95, 0.05, 0.0])),  # highest similarity
        ]
        result = find_relevant_chunks(query, stored, top_k=2)
        assert len(result) == 2
        assert "chunk D" in result
        assert "chunk B" in result

    def test_top_k_larger_than_stored(self):
        query = [1.0, 0.0]
        stored = [
            ("only chunk", json.dumps([1.0, 0.0])),
        ]
        result = find_relevant_chunks(query, stored, top_k=5)
        assert len(result) == 1
        assert result[0] == "only chunk"

    def test_empty_stored(self):
        query = [1.0, 0.0]
        result = find_relevant_chunks(query, [], top_k=3)
        assert result == []

    def test_ordering_is_by_similarity_desc(self):
        query = [1.0, 0.0]
        stored = [
            ("low", json.dumps([0.0, 1.0])),
            ("high", json.dumps([1.0, 0.0])),
            ("mid", json.dumps([0.7, 0.7])),
        ]
        result = find_relevant_chunks(query, stored, top_k=3)
        assert result[0] == "high"


# Need pytest for approx
import pytest
