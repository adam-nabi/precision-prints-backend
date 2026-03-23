import json
import os
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from .models import Order, OrderStatus, PricingSettings


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _data_dir() -> Path:
    custom_dir = os.getenv("DATA_DIR")
    if custom_dir:
        return Path(custom_dir)

    return DEFAULT_DATA_DIR


def _orders_file() -> Path:
    custom_file = os.getenv("ORDERS_FILE")
    if custom_file:
        return Path(custom_file)

    return _data_dir() / "orders.json"


def _pricing_file() -> Path:
    return _data_dir() / "pricing_settings.json"


def _reddit_seen_file() -> Path:
    return _data_dir() / "reddit_seen.json"


def _discord_seen_file() -> Path:
    return _data_dir() / "discord_seen.json"


def _ensure_data_dir() -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)


def load_orders() -> List[Order]:
    _ensure_data_dir()
    orders_file = _orders_file()

    if not orders_file.exists():
        return []

    with orders_file.open("r", encoding="utf-8") as file:
        raw_orders = json.load(file)

    return [Order.model_validate(item) for item in raw_orders]


def save_orders(orders: List[Order]) -> None:
    _ensure_data_dir()
    orders_file = _orders_file()

    with orders_file.open("w", encoding="utf-8") as file:
        json.dump(
            [order.model_dump(mode="json") for order in orders],
            file,
            indent=2,
        )


def create_order(order: Order) -> Order:
    orders = load_orders()
    orders.insert(0, order)
    save_orders(orders)
    return order


def get_order(order_id: UUID) -> Optional[Order]:
    for order in load_orders():
        if order.id == order_id:
            return order

    return None


def update_order_status(order_id: UUID, status: OrderStatus) -> Optional[Order]:
    orders = load_orders()

    for index, order in enumerate(orders):
        if order.id == order_id:
            updated_order = order.model_copy(update={"status": status})
            orders[index] = updated_order
            save_orders(orders)
            return updated_order

    return None


def save_order(updated_order: Order) -> Optional[Order]:
    orders = load_orders()

    for index, order in enumerate(orders):
        if order.id == updated_order.id:
            orders[index] = updated_order
            save_orders(orders)
            return updated_order

    return None


def delete_order(order_id: UUID) -> bool:
    orders = load_orders()
    remaining_orders = [order for order in orders if order.id != order_id]

    if len(remaining_orders) == len(orders):
        return False

    save_orders(remaining_orders)
    return True


def update_payment_link(order_id: UUID, payment_link_url: str) -> Optional[Order]:
    orders = load_orders()

    for index, order in enumerate(orders):
        if order.id == order_id:
            updated_order = order.model_copy(
                update={
                    "paymentLinkURL": payment_link_url,
                    "status": OrderStatus.PENDING_PAYMENT,
                }
            )
            orders[index] = updated_order
            save_orders(orders)
            return updated_order

    return None


def update_order_details(
    order_id: UUID,
    reply_draft: Optional[str] = None,
    selected_shipping_option: Optional[str] = None,
    shipping_name: Optional[str] = None,
    shipping_address: Optional[str] = None,
    shipping_zip: Optional[str] = None,
) -> Optional[Order]:
    orders = load_orders()

    for index, order in enumerate(orders):
        if order.id != order_id:
            continue

        updates = {
            "replyDraft": reply_draft if reply_draft is not None else order.replyDraft,
            "shippingName": shipping_name if shipping_name is not None else order.shippingName,
            "shippingAddress": shipping_address if shipping_address is not None else order.shippingAddress,
            "shippingZIP": shipping_zip if shipping_zip is not None else order.shippingZIP,
        }

        if selected_shipping_option:
            matching_option = next(
                (option for option in order.shippingOptions if option.name == selected_shipping_option),
                None,
            )
            if matching_option is not None:
                subtotal = max(order.totalAmount - order.shippingAmount, 0)
                updates["selectedShippingOption"] = matching_option.name
                updates["shippingAmount"] = matching_option.amount
                updates["totalAmount"] = round(subtotal + matching_option.amount, 2)

        updated_order = order.model_copy(update=updates)
        orders[index] = updated_order
        save_orders(orders)
        return updated_order

    return None


def load_pricing_settings() -> PricingSettings:
    _ensure_data_dir()
    pricing_file = _pricing_file()

    if not pricing_file.exists():
        default_settings = PricingSettings(
            baseOrderFee=5.0,
            materialMarkupMultiplier=1.35,
            hourlyPrintRate=4.0,
            complexitySurcharge=3.0,
            shippingMarkupFlat=1.5,
        )
        save_pricing_settings(default_settings)
        return default_settings

    with pricing_file.open("r", encoding="utf-8") as file:
        raw_settings = json.load(file)

    return PricingSettings.model_validate(raw_settings)


def save_pricing_settings(settings: PricingSettings) -> PricingSettings:
    _ensure_data_dir()
    pricing_file = _pricing_file()

    with pricing_file.open("w", encoding="utf-8") as file:
        json.dump(settings.model_dump(mode="json"), file, indent=2)

    return settings


def load_reddit_seen_ids() -> List[str]:
    _ensure_data_dir()
    seen_file = _reddit_seen_file()

    if not seen_file.exists():
        return []

    with seen_file.open("r", encoding="utf-8") as file:
        raw_ids = json.load(file)

    return [str(item) for item in raw_ids]


def save_reddit_seen_ids(post_ids: List[str]) -> None:
    _ensure_data_dir()
    seen_file = _reddit_seen_file()

    with seen_file.open("w", encoding="utf-8") as file:
        json.dump(sorted(set(post_ids)), file, indent=2)


def load_discord_seen_ids() -> List[str]:
    _ensure_data_dir()
    seen_file = _discord_seen_file()

    if not seen_file.exists():
        return []

    with seen_file.open("r", encoding="utf-8") as file:
        raw_ids = json.load(file)

    return [str(item) for item in raw_ids]


def save_discord_seen_ids(message_ids: List[str]) -> None:
    _ensure_data_dir()
    seen_file = _discord_seen_file()

    with seen_file.open("w", encoding="utf-8") as file:
        json.dump(sorted(set(message_ids)), file, indent=2)
