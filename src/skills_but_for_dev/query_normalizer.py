"""Query normalization and keyword distillation for GitHub and Hugging Face search."""

import re
from typing import NamedTuple

# Common English and Turkish filler/noise words in developer queries (normalized ASCII)
STOP_WORDS = {
    # English stop words & fillers
    "a", "an", "the", "and", "or", "to", "for", "in", "of", "with", "from", "by",
    "on", "at", "as", "is", "are", "was", "were", "be", "been", "that", "this",
    "which", "how", "what", "can", "could", "i", "we", "you", "my", "our", "want",
    "need", "looking", "best", "good", "fast", "simple", "easy", "tool", "library",
    "framework", "app", "application", "project", "repo", "system", "module",
    "using", "used", "make", "build", "create", "service", "microservice",

    # Turkish stop words & fillers (ASCII normalized)
    "bir", "ve", "veya", "ile", "icin", "olan", "yapan", "eden", "nasil",
    "hangi", "en", "iyi", "hizli", "araci", "kutuphanesi", "kutuphane",
    "uygulama", "proje", "istiyorum", "lazim", "gerekli", "yapmak", "kurmak",
    "gelistirmek", "sirket", "sistem", "paket", "servis", "ici", "okuyan",
    "okur", "yerel", "yerli", "bu", "su", "o", "gibi", "kadar", "icin",
}

# Programming language tokens mapped to GitHub language search filters
PROGRAMMING_LANGUAGES = {
    "python": "python",
    "typescript": "typescript",
    "javascript": "javascript",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "go": "go",
    "rust": "rust",
    "cpp": "c++",
    "c++": "c++",
    "csharp": "c#",
    "c#": "c#",
    "java": "java",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
    "kotlin": "kotlin",
}

# Common technical intent mappings (Turkish/informal -> canonical tech term)
CANONICAL_SYNONYMS = {
    "fatura": "invoice",
    "faturalar": "invoice",
    "invoices": "invoice",
    "makbuz": "receipt",
    "receipts": "receipt",
    "metin": "text",
    "ses": "audio",
    "sesli": "voice",
    "görsel": "vision",
    "gorsel": "vision",
    "resim": "image",
    "images": "image",
    "belge": "document",
    "belgeler": "document",
    "documents": "document",
    "tablo": "table",
    "tablolar": "table",
    "tables": "table",
}

TURKISH_CHAR_MAP = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
})


def _normalize_token(token: str) -> str:
    """Normalize accents and Turkish characters to canonical ASCII."""
    ascii_token = token.translate(TURKISH_CHAR_MAP).lower()
    return CANONICAL_SYNONYMS.get(ascii_token, CANONICAL_SYNONYMS.get(token.lower(), ascii_token))


class NormalizedQuery(NamedTuple):
    cleaned_query: str
    terms: list[str]
    is_modified: bool
    detected_language: str | None = None


def normalize_query(query: str, max_terms: int = 3) -> NormalizedQuery:
    """Clean natural-language queries into 2-3 high-density technical keywords.

    GitHub search syntax treats spaces as strict AND operators. Queries with 4+ words
    frequently return 0 results. This function strips noise words, extracts programming
    language filters, and preserves domain-specific terminology.

    Example:
        'I want a fast python tool to parse pdf invoices'
        -> terms: ['parse', 'pdf', 'invoice'], detected_language: 'python'
    """
    raw = query.strip()
    if not raw:
        return NormalizedQuery(cleaned_query="", terms=[], is_modified=False, detected_language=None)

    # Clean punctuation and lowercase
    cleaned = re.sub(r"[^\w\s-]", " ", raw)
    raw_tokens = [t for t in re.split(r"[\s_]+", cleaned) if t]

    meaningful: list[str] = []
    detected_language: str | None = None

    for token in raw_tokens:
        normalized = _normalize_token(token)

        # Extract language filter instead of wasting a term slot
        if normalized in PROGRAMMING_LANGUAGES and detected_language is None:
            detected_language = PROGRAMMING_LANGUAGES[normalized]
            continue

        if normalized not in STOP_WORDS and len(normalized) > 1:
            if normalized not in meaningful:
                meaningful.append(normalized)

    # Fallback to original tokens if all were pruned
    if not meaningful:
        meaningful = [_normalize_token(t) for t in raw_tokens[:max_terms]]

    selected_terms = meaningful[:max_terms]
    cleaned_str = " ".join(selected_terms)
    is_modified = cleaned_str.lower() != raw.lower()

    return NormalizedQuery(
        cleaned_query=cleaned_str,
        terms=selected_terms,
        is_modified=is_modified,
        detected_language=detected_language,
    )
