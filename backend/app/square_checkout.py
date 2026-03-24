import json
import os
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .models import Order


SQUARE_API_BASE = "https://connect.squareup.com/v2"


def square_is_configured() -> bool:
    return bool(os.getenv("SQUARE_ACCESS_TOKEN") and os.getenv("SQUARE_LOCATION_ID"))


def create_square_payment_link(order: Order, base_url: str) -> str:
    access_token = os.getenv("SQUARE_ACCESS_TOKEN")
    location_id = os.getenv("SQUARE_LOCATION_ID")
    if not access_token or not location_id:
        raise RuntimeError("Square is not configured.")

    amount_cents = _to_cents(order.totalAmount)
    if amount_cents <= 0:
        raise RuntimeError("Order total must be greater than zero.")

    payload = {
        "idempotency_key": str(uuid4()),
        "quick_pay": {
            "name": f"Precision Prints - {order.fileName}",
            "price_money": {
                "amount": amount_cents,
                "currency": "USD",
            },
            "location_id": location_id,
        },
        "checkout_options": {
            "redirect_url": f"{base_url.rstrip('/')}/quote/{order.id}",
            "merchant_support_email": os.getenv("BUSINESS_SUPPORT_EMAIL", "info@precisionprints.tech"),
        },
        "pre_populated_data": {
            "buyer_email": getattr(order, "customerEmail", None) or "",
        },
    }

    request = Request(
        url=f"{SQUARE_API_BASE}/online-checkout/payment-links",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Square-Version": os.getenv("SQUARE_API_VERSION", "2025-10-16"),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Square error: {details or error.reason}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Square: {error.reason}") from error

    payment_link = data.get("payment_link", {})
    url = payment_link.get("url")
    if not url:
        raise RuntimeError("Square did not return a payment link.")

    return url


def _to_cents(amount: float) -> int:
    decimal_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(decimal_amount * 100)
