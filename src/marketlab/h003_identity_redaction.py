from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

LEGAL_SUFFIX_PATTERN = re.compile(
    r"\s+(?:limited|ltd\.?|private limited|pvt\.? ltd\.?)$", re.IGNORECASE
)
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9.'’&-]*")
SPEAKER_LABEL_PATTERN = re.compile(
    r"(?<!\w)([A-Z][A-Za-z.'’&-]*(?:\s+[A-Z][A-Za-z.'’&-]*){1,4})\s*:"
)

# These are generic corporate/industry descriptors, not identity-bearing tokens.
# Full legal/root company names are still redacted. This set only prevents an
# ordinary word such as "vehicles" from being promoted to a standalone alias.
GENERIC_COMPANY_WORDS = frozenset(
    {
        "and",
        "auto",
        "automobile",
        "automobiles",
        "aviation",
        "beverage",
        "beverages",
        "cement",
        "cements",
        "chemical",
        "chemicals",
        "co",
        "communications",
        "communication",
        "company",
        "construction",
        "consumer",
        "corp",
        "corporation",
        "developer",
        "developers",
        "development",
        "electric",
        "electrical",
        "electronics",
        "energy",
        "engineering",
        "enterprise",
        "enterprises",
        "food",
        "foods",
        "health",
        "healthcare",
        "holding",
        "holdings",
        "hospital",
        "hospitals",
        "hotel",
        "hotels",
        "india",
        "indian",
        "industries",
        "industry",
        "infra",
        "infrastructure",
        "laboratories",
        "laboratory",
        "limited",
        "logistics",
        "ltd",
        "material",
        "materials",
        "metal",
        "metals",
        "mining",
        "motor",
        "motors",
        "of",
        "paint",
        "paints",
        "paper",
        "pharma",
        "pharmaceutical",
        "pharmaceuticals",
        "port",
        "ports",
        "power",
        "private",
        "product",
        "products",
        "properties",
        "property",
        "pvt",
        "realty",
        "retail",
        "service",
        "services",
        "shipping",
        "solution",
        "solutions",
        "steel",
        "system",
        "systems",
        "technology",
        "technologies",
        "telecom",
        "textile",
        "textiles",
        "the",
        "tube",
        "tubes",
        "tyre",
        "tyres",
        "vehicle",
        "vehicles",
    }
)


class H003IdentityRedactionError(ValueError):
    """Raised when explicit identity survives an H003 blind packet."""


def _normalized_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def company_redaction_terms(member: dict[str, Any], symbol: str) -> tuple[str, ...]:
    name = str(member.get("company_name") or "").strip()
    root = LEGAL_SUFFIX_PATTERN.sub("", name).strip()
    variants = {
        symbol.strip(),
        name,
        root,
        name.replace("Ltd.", "Limited"),
        name.replace("Ltd", "Limited"),
        root.replace("&", "and"),
        root.replace("and", "&"),
    }

    tokens = TOKEN_PATTERN.findall(root)
    trimmed = list(tokens)
    while trimmed and _normalized_word(trimmed[-1]) in GENERIC_COMPANY_WORDS:
        trimmed.pop()
    if trimmed:
        variants.add(" ".join(trimmed))
        variants.add(" ".join(trimmed).replace(" & ", " and "))
        variants.add(" ".join(trimmed).replace(" and ", " & "))

    for token in tokens:
        normalized = _normalized_word(token)
        if len(normalized) >= 4 and normalized not in GENERIC_COMPANY_WORDS:
            variants.add(token)

    # Preserve useful multi-token prefixes even where the first token is a short
    # acronym, for example "APL Apollo" from "APL Apollo Tubes Limited".
    if len(trimmed) >= 2:
        for end in range(2, len(trimmed) + 1):
            prefix = " ".join(trimmed[:end]).strip()
            if len(_normalized_word(prefix)) >= 6:
                variants.add(prefix)

    return tuple(
        sorted(
            {item.strip() for item in variants if item and item.strip()},
            key=lambda item: (-len(item), item.casefold()),
        )
    )


def speaker_redaction_terms(selected: Iterable[Any]) -> tuple[str, ...]:
    terms: set[str] = set()
    for item in selected:
        passage = getattr(item, "passage", None)
        text = str(getattr(passage, "text", "") or "")
        for match in SPEAKER_LABEL_PATTERN.finditer(text):
            label = " ".join(match.group(1).split())
            if label:
                terms.add(label)
    return tuple(sorted(terms, key=lambda item: (-len(item), item.casefold())))


def combined_redaction_terms(
    member: dict[str, Any],
    symbol: str,
    selected: Iterable[Any],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *company_redaction_terms(member, symbol),
                *speaker_redaction_terms(selected),
            },
            key=lambda item: (-len(item), item.casefold()),
        )
    )


def assert_identity_scrubbed(packet_document: dict[str, Any], terms: Iterable[str]) -> None:
    rendered = __import__("json").dumps(packet_document, ensure_ascii=False)
    for term in terms:
        cleaned = str(term).strip()
        if not cleaned:
            continue
        pattern = rf"(?<!\w){re.escape(cleaned)}(?!\w)"
        if re.search(pattern, rendered, flags=re.IGNORECASE):
            raise H003IdentityRedactionError(
                f"explicit identity term survived blind packet: {cleaned!r}"
            )

    evidence = packet_document.get("evidence")
    if not isinstance(evidence, list):
        raise H003IdentityRedactionError("blind packet evidence must be a list")
    for passage in evidence:
        if not isinstance(passage, dict):
            raise H003IdentityRedactionError("blind packet evidence row must be an object")
        text = str(passage.get("text") or "")
        surviving_labels = [
            " ".join(match.group(1).split()) for match in SPEAKER_LABEL_PATTERN.finditer(text)
        ]
        if surviving_labels:
            raise H003IdentityRedactionError(
                f"speaker labels survived blind packet: {surviving_labels[:3]}"
            )
