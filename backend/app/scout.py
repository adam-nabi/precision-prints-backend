import re
from dataclasses import dataclass
from typing import Optional


ALLOWED_SOURCES = {"Reddit", "Discord"}
ALLOWED_MATERIALS = ("PLA", "PETG")

_MODEL_DOMAINS = (
    "thingiverse.com",
    "printables.com",
    "makerworld.com",
    "cults3d.com",
    "thangs.com",
)
_MODEL_EXTENSIONS = (".stl", ".3mf", ".zip")
_PRINT_INTENT_PATTERNS = (
    r"\b3d\s*print(?:ed|ing)?\b",
    r"\bcan (?:someone|anyone) print\b",
    r"\bneed(?: this)? printed\b",
    r"\blooking for someone to print\b",
    r"\bwho can print\b",
    r"\bwant(?: this)? printed\b",
    r"\bprint this\b",
    r"\bquote(?: me)?\b",
)
_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_UNSUPPORTED_MATERIAL_PATTERNS = {
    "ASA": r"\basa\b",
    "ABS": r"\babs\b",
    "Resin": r"\bresin\b",
    "TPU": r"\btpu\b",
    "Nylon": r"\bnylon\b",
    "Carbon Fiber": r"\b(?:cf|carbon[\s-]?fiber)\b",
}


@dataclass
class ScoutMatch:
    matched: bool
    reason: str
    detected_model_url: Optional[str] = None
    detected_material: Optional[str] = None
    unsupported_material: Optional[str] = None


def analyze_message(message_text: str, source_url: Optional[str] = None) -> ScoutMatch:
    normalized_text = message_text.lower()
    urls = _extract_urls(message_text)
    combined_urls = urls + ([source_url] if source_url else [])
    model_url = next((url for url in combined_urls if _is_model_url(url)), None)
    has_print_intent = any(re.search(pattern, normalized_text) for pattern in _PRINT_INTENT_PATTERNS)
    detected_material = _detect_allowed_material(normalized_text)
    unsupported_material = _detect_unsupported_material(normalized_text)

    if model_url and has_print_intent:
        return ScoutMatch(
            matched=True,
            reason="Found a print request with a model link.",
            detected_model_url=model_url,
            detected_material=detected_material,
            unsupported_material=unsupported_material,
        )

    if has_print_intent:
        return ScoutMatch(
            matched=True,
            reason="Found a print request, but the model link is missing.",
            detected_material=detected_material,
            unsupported_material=unsupported_material,
        )

    return ScoutMatch(matched=False, reason="Message does not look like a print request.")


def build_reply_draft(customer_name: str, model_url: Optional[str], unsupported_material: Optional[str]) -> str:
    first_name = customer_name.split()[0]

    if unsupported_material:
        return (
            f"Hi {first_name}, thanks for reaching out. "
            f"I only offer PLA and PETG printing right now, not {unsupported_material}. "
            "If PLA or PETG works for your part, send your preferred color, quantity, and shipping ZIP code "
            "and I can put together the quote."
        )

    if model_url:
        return (
            f"Hi {first_name}, thanks for sharing the model link. "
            "I can quote this in PLA or PETG. "
            "Please send your preferred color, quantity, and shipping ZIP code."
        )

    return (
        f"Hi {first_name}, thanks for reaching out. "
        "Please send the STL, 3MF, ZIP, Thingiverse, Printables, or MakerWorld link, "
        "plus whether you want PLA or PETG, your color choice, quantity, and shipping ZIP code."
    )


def resolve_order_material(detected_material: Optional[str], unsupported_material: Optional[str]) -> str:
    if detected_material:
        return detected_material

    if unsupported_material:
        return f"Unsupported: {unsupported_material}"

    return "PLA or PETG"


def build_notes(source: str, message_text: str, source_url: Optional[str], unsupported_material: Optional[str]) -> str:
    note_lines = [f"Imported lead from {source}."]

    if source_url:
        note_lines.append(f"Source URL: {source_url}")

    if unsupported_material:
        note_lines.append(f"Requested unsupported material: {unsupported_material}. Only PLA and PETG are allowed.")

    note_lines.append("Original message:")
    note_lines.append(message_text)

    return "\n".join(note_lines)


def _extract_urls(text: str) -> list[str]:
    return [match.rstrip(".,!?)]}") for match in _URL_PATTERN.findall(text)]


def _is_model_url(url: str) -> bool:
    lowered = url.lower()
    return any(domain in lowered for domain in _MODEL_DOMAINS) or lowered.endswith(_MODEL_EXTENSIONS)


def _detect_allowed_material(message_text: str) -> Optional[str]:
    if re.search(r"\bpetg\b", message_text):
        return "PETG"

    if re.search(r"\bpla(?:\+)?\b", message_text):
        return "PLA"

    return None


def _detect_unsupported_material(message_text: str) -> Optional[str]:
    for material_name, pattern in _UNSUPPORTED_MATERIAL_PATTERNS.items():
        if re.search(pattern, message_text):
            return material_name

    return None
