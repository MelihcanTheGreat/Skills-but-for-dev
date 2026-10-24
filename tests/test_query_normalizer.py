"""Unit tests for query normalization and technical keyword distillation."""

from skills_but_for_dev.query_normalizer import normalize_query


def test_normalize_empty_query():
    norm = normalize_query("")
    assert norm.cleaned_query == ""
    assert norm.terms == []
    assert not norm.is_modified

    norm_spaces = normalize_query("   ")
    assert norm_spaces.cleaned_query == ""
    assert norm_spaces.terms == []


def test_normalize_english_natural_language():
    query = "I want a fast tool to parse pdf invoices"
    norm = normalize_query(query, max_terms=3)
    # Stop words "I", "want", "a", "fast", "tool", "to" should be stripped
    assert "pdf" in norm.terms
    assert "invoice" in norm.terms
    assert "parse" in norm.terms
    assert len(norm.terms) <= 3
    assert norm.is_modified


def test_normalize_turkish_natural_language_and_synonyms():
    # "fatura" -> "invoice", "şirket", "içi", "okuyan", "yerel", "aracı" are stop words
    query = "şirket içi fatura okuyan yerel ocr aracı"
    norm = normalize_query(query, max_terms=3)
    assert "invoice" in norm.terms
    assert "ocr" in norm.terms
    assert norm.is_modified


def test_normalize_preserves_short_clean_keywords():
    query = "whisper diarization"
    norm = normalize_query(query)
    assert norm.cleaned_query == "whisper diarization"
    assert norm.terms == ["whisper", "diarization"]


def test_normalize_all_stop_words_fallback():
    # If all tokens are stop words, function falls back to first tokens so query isn't empty
    query = "the good best"
    norm = normalize_query(query, max_terms=2)
    assert len(norm.terms) > 0
    assert norm.cleaned_query != ""


def test_normalize_handles_punctuation_and_symbols():
    query = "fastapi + postgresql (async)!!!"
    norm = normalize_query(query, max_terms=3)
    assert "fastapi" in norm.terms
    assert "postgresql" in norm.terms
    assert "async" in norm.terms
