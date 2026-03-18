import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from .models import PricingSettings
from .page_extractors import ExtractedLinkResult, extract_direct_file_url


BASE_SHIPPING_ESTIMATE = 4.50
SUPPORTED_DIRECT_EXTENSIONS = {".stl", ".3mf", ".zip"}
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PrecisionPrintsBot/0.1"
}


@dataclass
class DownloadQuoteResult:
    downloaded: bool
    reason: str
    file_name: Optional[str] = None
    downloaded_file_path: Optional[str] = None
    estimated_print_hours: Optional[float] = None
    estimated_material_grams: Optional[float] = None
    shipping_amount: Optional[float] = None
    total_amount: Optional[float] = None


def process_model_url(
    order_id: UUID,
    model_url: Optional[str],
    quantity: int,
    pricing_settings: PricingSettings,
) -> DownloadQuoteResult:
    if not model_url:
        return DownloadQuoteResult(
            downloaded=False,
            reason="No model link was provided, so the file could not be downloaded or quoted yet.",
        )

    resolved_model_url = model_url
    parsed_url = urlparse(resolved_model_url)
    extension = Path(parsed_url.path).suffix.lower()
    file_name = PurePosixPath(parsed_url.path).name or "linked-model"
    extraction_reason: Optional[str] = None

    if extension not in SUPPORTED_DIRECT_EXTENSIONS:
        extraction_result = _extract_from_model_page(resolved_model_url)
        extraction_reason = extraction_result.reason

        if not extraction_result.direct_file_url:
            review_url = extraction_result.display_page_url or resolved_model_url
            return DownloadQuoteResult(
                downloaded=False,
                reason=f"{extraction_result.reason} Review link: {review_url}",
                file_name=file_name,
            )

        resolved_model_url = extraction_result.direct_file_url
        parsed_url = urlparse(resolved_model_url)
        extension = Path(parsed_url.path).suffix.lower()
        file_name = PurePosixPath(parsed_url.path).name or file_name

    if extension not in SUPPORTED_DIRECT_EXTENSIONS:
        return DownloadQuoteResult(
            downloaded=False,
            reason="The extracted download link was not an STL, 3MF, or ZIP file.",
            file_name=file_name,
        )

    downloads_dir = _downloads_dir() / str(order_id)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    local_file_path = downloads_dir / file_name

    try:
        with urlopen(Request(resolved_model_url, headers=REQUEST_HEADERS), timeout=25) as response:
            data = response.read()
    except HTTPError as error:
        return DownloadQuoteResult(
            downloaded=False,
            reason=f"Download failed with HTTP {error.code}.",
            file_name=file_name,
        )
    except URLError:
        return DownloadQuoteResult(
            downloaded=False,
            reason="Download failed because the model host could not be reached.",
            file_name=file_name,
        )

    local_file_path.write_bytes(data)

    size_bytes = max(len(data), 1)
    size_mb = size_bytes / (1024 * 1024)
    estimated_material_grams = round(max(size_mb * 45, 12) * max(quantity, 1), 1)
    estimated_print_hours = round(max(size_mb * 1.2, 0.6) * max(quantity, 1), 1)

    material_cost = estimated_material_grams * 0.06 * pricing_settings.materialMarkupMultiplier
    print_cost = estimated_print_hours * pricing_settings.hourlyPrintRate
    complexity_cost = pricing_settings.complexitySurcharge if extension in {".3mf", ".zip"} else 0
    subtotal = pricing_settings.baseOrderFee + material_cost + print_cost + complexity_cost
    shipping_amount = round(BASE_SHIPPING_ESTIMATE + pricing_settings.shippingMarkupFlat, 2)
    total_amount = round(subtotal + shipping_amount, 2)

    return DownloadQuoteResult(
        downloaded=True,
        reason=_build_success_reason(extraction_reason),
        file_name=file_name,
        downloaded_file_path=str(local_file_path),
        estimated_print_hours=estimated_print_hours,
        estimated_material_grams=estimated_material_grams,
        shipping_amount=shipping_amount,
        total_amount=total_amount,
    )


def _downloads_dir() -> Path:
    custom_dir = os.getenv("DOWNLOADS_DIR")
    if custom_dir:
        return Path(custom_dir)

    return Path(__file__).resolve().parent.parent / "data" / "downloads"


def _extract_from_model_page(model_url: str) -> ExtractedLinkResult:
    try:
        with urlopen(Request(model_url, headers=REQUEST_HEADERS), timeout=25) as response:
            html_text = response.read().decode("utf-8", errors="ignore")
    except HTTPError as error:
        return ExtractedLinkResult(
            direct_file_url=None,
            display_page_url=model_url,
            reason=f"Model page fetch failed with HTTP {error.code}.",
        )
    except URLError:
        return ExtractedLinkResult(
            direct_file_url=None,
            display_page_url=model_url,
            reason="Model page fetch failed because the host could not be reached.",
        )

    return extract_direct_file_url(model_url, html_text)


def _build_success_reason(extraction_reason: Optional[str]) -> str:
    if extraction_reason:
        return f"{extraction_reason} The model file was then downloaded and rough pricing was created."

    return "Model file downloaded and rough quote created from the direct file link."
