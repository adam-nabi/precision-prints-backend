import json
import re
from dataclasses import dataclass
from html import unescape
from typing import List, Optional
from urllib.parse import urljoin, urlparse


SUPPORTED_DIRECT_EXTENSIONS = (".stl", ".3mf", ".zip")


@dataclass
class ExtractedLinkResult:
    direct_file_url: Optional[str]
    display_page_url: Optional[str]
    reason: str


def extract_direct_file_url(page_url: str, html_text: str) -> ExtractedLinkResult:
    lowered_url = page_url.lower()

    if "printables.com" in lowered_url:
        return _extract_printables(page_url, html_text)

    if "makerworld.com" in lowered_url:
        return _extract_makerworld(page_url, html_text)

    return ExtractedLinkResult(
        direct_file_url=None,
        display_page_url=page_url,
        reason="No extractor is available for this model page yet.",
    )


def _extract_printables(page_url: str, html_text: str) -> ExtractedLinkResult:
    file_urls = _find_direct_file_urls(page_url, html_text)
    if file_urls:
        return ExtractedLinkResult(
            direct_file_url=file_urls[0],
            display_page_url=_printables_files_page(page_url),
            reason="Extracted a direct file link from the Printables page.",
        )

    return ExtractedLinkResult(
        direct_file_url=None,
        display_page_url=_printables_files_page(page_url),
        reason=(
            "This is a Printables model page. I found the files page, but I could not extract a direct STL, 3MF, "
            "or ZIP download link from the current page HTML."
        ),
    )


def _extract_makerworld(page_url: str, html_text: str) -> ExtractedLinkResult:
    file_urls = _find_direct_file_urls(page_url, html_text)
    if file_urls:
        return ExtractedLinkResult(
            direct_file_url=file_urls[0],
            display_page_url=page_url,
            reason="Extracted a direct file link from the MakerWorld page.",
        )

    return ExtractedLinkResult(
        direct_file_url=None,
        display_page_url=page_url,
        reason=(
            "This is a MakerWorld model page. I could not extract a direct STL, 3MF, or ZIP download link from the "
            "current page HTML."
        ),
    )


def _find_direct_file_urls(page_url: str, html_text: str) -> List[str]:
    candidates: List[str] = []

    for raw_url in _extract_json_urls(html_text):
        normalized = _normalize_url(page_url, raw_url)
        if _is_direct_file_url(normalized):
            candidates.append(normalized)

    for raw_url in re.findall(r'https?://[^"\'>\s]+', html_text, flags=re.IGNORECASE):
        normalized = _normalize_url(page_url, raw_url)
        if _is_direct_file_url(normalized):
            candidates.append(normalized)

    for raw_url in re.findall(r'/(?:[^"\'>\s]+)', html_text):
        normalized = _normalize_url(page_url, raw_url)
        if _is_direct_file_url(normalized):
            candidates.append(normalized)

    return _unique(candidates)


def _extract_json_urls(html_text: str) -> List[str]:
    json_urls: List[str] = []

    patterns = [
        r'"downloadUrl"\s*:\s*"([^"]+)"',
        r'"download_url"\s*:\s*"([^"]+)"',
        r'"url"\s*:\s*"([^"]+\.(?:stl|3mf|zip)(?:\?[^"]*)?)"',
        r'"files"\s*:\s*(\[[^\]]+\])',
    ]

    for pattern in patterns:
        for match in re.findall(pattern, html_text, flags=re.IGNORECASE):
            if match.startswith("["):
                try:
                    items = json.loads(match)
                except json.JSONDecodeError:
                    continue
                for item in items:
                    if isinstance(item, dict):
                        for value in item.values():
                            if isinstance(value, str):
                                json_urls.append(value)
            else:
                json_urls.append(match)

    return json_urls


def _normalize_url(page_url: str, url: str) -> str:
    cleaned = unescape(url).replace("\\/", "/")
    return urljoin(page_url, cleaned)


def _is_direct_file_url(url: str) -> bool:
    lowered = url.lower()
    parsed = urlparse(lowered)
    return parsed.scheme in {"http", "https", "file"} and any(
        parsed.path.endswith(extension) for extension in SUPPORTED_DIRECT_EXTENSIONS
    )


def _printables_files_page(page_url: str) -> str:
    parsed = urlparse(page_url)
    if parsed.path.endswith("/files"):
        return page_url

    trimmed_path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{trimmed_path}/files"


def _unique(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
