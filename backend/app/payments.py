import os

import stripe

from .models import Order, OrderStatus


def _amount_to_cents(amount: float) -> int:
    return max(0, int(round(amount * 100)))


def _allowed_countries() -> list[str]:
    countries = os.getenv("PAYMENT_LINK_ALLOWED_COUNTRIES", "US")
    return [country.strip().upper() for country in countries.split(",") if country.strip()]


def create_payment_link(order: Order) -> Order:
    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set.")

    stripe.api_key = api_key

    print_subtotal = max(order.totalAmount - order.shippingAmount, 0)

    create_params = {
        "line_items": [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"3D print order: {order.fileName}",
                        "description": f"{order.material} / {order.color} / Qty {order.quantity}",
                    },
                    "unit_amount": _amount_to_cents(print_subtotal),
                },
                "quantity": 1,
            }
        ],
        "billing_address_collection": "required",
        "shipping_address_collection": {
            "allowed_countries": _allowed_countries(),
        },
        "metadata": {
            "order_id": str(order.id),
            "customer_name": order.customerName,
            "file_name": order.fileName,
        },
    }

    if order.shippingAmount > 0:
        create_params["shipping_options"] = [
            {
                "shipping_rate_data": {
                    "type": "fixed_amount",
                    "fixed_amount": {
                        "amount": _amount_to_cents(order.shippingAmount),
                        "currency": "usd",
                    },
                    "display_name": "Shipping",
                    "delivery_estimate": {
                        "minimum": {"unit": "business_day", "value": 3},
                        "maximum": {"unit": "business_day", "value": 7},
                    },
                }
            }
        ]

    payment_link = stripe.PaymentLink.create(**create_params)

    return order.model_copy(
        update={
            "paymentLinkURL": payment_link.url,
            "status": OrderStatus.PENDING_PAYMENT,
        }
    )
