"""SPDX and Hugging Face license classification."""


from stack_scout.models import LicenseClass

PERMISSIVE_SPDX = {
    "mit",
    "apache-2.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "unlicense",
    "cc0-1.0",
    "0bsd",
    "zlib",
    "artistic-2.0",
    "wtfpl",
}

WEAK_COPYLEFT_SPDX = {
    "lgpl-2.0",
    "lgpl-2.1",
    "lgpl-3.0",
    "mpl-2.0",
    "epl-1.0",
    "epl-2.0",
    "cddl-1.0",
    "cddl-1.1",
}

STRONG_COPYLEFT_SPDX = {
    "gpl-2.0",
    "gpl-3.0",
    "agpl-3.0",
    "osl-3.0",
    "sspl-1.0",
    "eupl-1.1",
    "eupl-1.2",
}

NON_COMMERCIAL_PATTERNS = [
    "cc-by-nc",
    "non-commercial",
    "research-only",
    "academic",
]

CUSTOM_AI_LICENSES = [
    "llama",
    "gemma",
    "openrail",
    "deepseek",
    "mistral",
    "bigscience",
]


def classify_license(spdx_or_name: str | None) -> LicenseClass:
    """Classify a license SPDX string or raw license name into standardized LicenseClass."""
    if not spdx_or_name or spdx_or_name.strip().upper() in ("NOASSERTION", "NONE", ""):
        return "unknown"

    cleaned = spdx_or_name.strip().lower()

    if cleaned in PERMISSIVE_SPDX:
        return "permissive"

    if cleaned in WEAK_COPYLEFT_SPDX:
        return "weak_copyleft"

    if cleaned in STRONG_COPYLEFT_SPDX:
        return "strong_copyleft"

    for pattern in NON_COMMERCIAL_PATTERNS:
        if pattern in cleaned:
            return "non_commercial"

    for pattern in CUSTOM_AI_LICENSES:
        if pattern in cleaned:
            return "custom"

    if any(k in cleaned for k in ["mit", "apache", "bsd"]):
        return "permissive"
    if "agpl" in cleaned or "gpl" in cleaned:
        return "strong_copyleft"

    return "unknown"


def is_commercially_viable(license_class: LicenseClass) -> bool:
    """Check if the license class is unconditionally safe for commercial use."""
    return license_class in ("permissive", "weak_copyleft")
