from pathlib import PurePosixPath
from uuid import UUID, uuid4
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    IntakeLeadRequest,
    Order,
    OrderStatus,
    PricingSettings,
    RedditScanResponse,
    ScoutMessageRequest,
    ScoutMessageResponse,
    UpdatePaymentLinkRequest,
    UpdatePricingSettingsRequest,
    UpdateStatusRequest,
)
from .model_worker import process_model_url
from .reddit_ingest import RedditConfigError, fetch_recent_posts
from .scout import ALLOWED_SOURCES, analyze_message, build_notes, build_reply_draft, resolve_order_material
from .store import (
    create_order,
    delete_order,
    get_order,
    load_orders,
    load_pricing_settings,
    load_reddit_seen_ids,
    save_pricing_settings,
    save_reddit_seen_ids,
    save_order,
    update_order_status,
    update_payment_link,
)


app = FastAPI(
    title="Precision Prints Backend",
    version="0.1.0",
    description="Small backend for the Precision Prints internal dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/orders", response_model=List[Order])
def list_orders() -> List[Order]:
    return load_orders()


@app.post("/scout/messages", response_model=ScoutMessageResponse)
def scout_message(request: ScoutMessageRequest) -> ScoutMessageResponse:
    if request.source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Only Reddit and Discord are supported right now.")

    match = analyze_message(request.messageText, request.sourceURL)
    if not match.matched:
        return ScoutMessageResponse(
            matched=False,
            reason=match.reason,
            detectedModelURL=match.detected_model_url,
            detectedMaterial=match.detected_material,
            unsupportedMaterial=match.unsupported_material,
        )

    imported_order = _build_order_from_lead(
        source=request.source,
        customer_name=request.customerName,
        message_text=request.messageText,
        source_url=request.sourceURL,
        model_url=match.detected_model_url,
        file_name=None,
        quantity=1,
        detected_material=match.detected_material,
        unsupported_material=match.unsupported_material,
        color_preference=None,
    )
    saved_order = _create_and_process_order(imported_order)

    return ScoutMessageResponse(
        matched=True,
        reason=match.reason,
        order=saved_order,
        detectedModelURL=match.detected_model_url,
        detectedMaterial=match.detected_material,
        unsupportedMaterial=match.unsupported_material,
    )


@app.post("/integrations/reddit/scan", response_model=RedditScanResponse)
def scan_reddit() -> RedditScanResponse:
    try:
        posts = fetch_recent_posts()
    except RedditConfigError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    seen_post_ids = set(load_reddit_seen_ids())
    created_orders: List[Order] = []
    scanned_posts = 0

    for post in posts:
        scanned_posts += 1
        if not post.post_id or post.post_id in seen_post_ids:
            continue

        message_text = _reddit_message_text(post)
        match = analyze_message(message_text, post.outbound_url or post.permalink)
        seen_post_ids.add(post.post_id)

        if not match.matched:
            continue

        imported_order = _build_order_from_lead(
            source="Reddit",
            customer_name=post.author,
            message_text=message_text,
            source_url=post.permalink,
            model_url=match.detected_model_url,
            file_name=None,
            quantity=1,
            detected_material=match.detected_material,
            unsupported_material=match.unsupported_material,
            color_preference=None,
        )
        created_orders.append(_create_and_process_order(imported_order))

    save_reddit_seen_ids(list(seen_post_ids))

    imported_count = len(created_orders)
    return RedditScanResponse(
        scannedPosts=scanned_posts,
        importedOrders=imported_count,
        skippedPosts=max(scanned_posts - imported_count, 0),
        summary=f"Scanned {scanned_posts} Reddit posts and created {imported_count} order(s).",
        createdOrders=created_orders,
    )


@app.post("/lead-intake", response_model=Order, status_code=201)
def intake_lead(request: IntakeLeadRequest) -> Order:
    analyzed_match = analyze_message(request.messageText, request.sourceURL)
    imported_order = _build_order_from_lead(
        source=request.source,
        customer_name=request.customerName,
        message_text=request.messageText,
        source_url=request.sourceURL,
        model_url=request.modelURL or analyzed_match.detected_model_url,
        file_name=request.fileName,
        quantity=max(request.quantity or 1, 1),
        detected_material=_resolve_requested_material(request.materialPreference, analyzed_match.detected_material),
        unsupported_material=_resolve_unsupported_material(request.materialPreference, analyzed_match.unsupported_material),
        color_preference=request.colorPreference,
    )
    return _create_and_process_order(imported_order)


@app.get("/orders/{order_id}", response_model=Order)
def fetch_order(order_id: UUID) -> Order:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@app.delete("/orders/{order_id}", status_code=204)
def remove_order(order_id: UUID) -> None:
    did_delete = delete_order(order_id)
    if not did_delete:
        raise HTTPException(status_code=404, detail="Order not found")


@app.patch("/orders/{order_id}/status", response_model=Order)
def patch_order_status(order_id: UUID, request: UpdateStatusRequest) -> Order:
    updated_order = update_order_status(order_id, request.status)
    if updated_order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return updated_order


@app.patch("/orders/{order_id}/payment-link", response_model=Order)
def patch_order_payment_link(order_id: UUID, request: UpdatePaymentLinkRequest) -> Order:
    updated_order = update_payment_link(order_id, request.paymentLinkURL)
    if updated_order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return updated_order


@app.get("/pricing-settings", response_model=PricingSettings)
def fetch_pricing_settings() -> PricingSettings:
    return load_pricing_settings()


@app.put("/pricing-settings", response_model=PricingSettings)
def put_pricing_settings(request: UpdatePricingSettingsRequest) -> PricingSettings:
    settings = PricingSettings.model_validate(request.model_dump())
    return save_pricing_settings(settings)


def _build_order_from_lead(
    source: str,
    customer_name: str,
    message_text: str,
    source_url: Optional[str],
    model_url: Optional[str],
    file_name: Optional[str],
    quantity: int,
    detected_material: Optional[str],
    unsupported_material: Optional[str],
    color_preference: Optional[str],
) -> Order:
    return Order(
        id=uuid4(),
        customerName=customer_name,
        source=source,
        fileName=_lead_file_name(file_name, model_url),
        material=resolve_order_material(detected_material, unsupported_material),
        color=color_preference or "Not specified",
        quantity=max(quantity, 1),
        shippingAmount=0.0,
        totalAmount=0.0,
        status=_lead_status(model_url, unsupported_material),
        replyDraft=build_reply_draft(customer_name, model_url, unsupported_material),
        modelDownloadURL=model_url,
        notes=build_notes(source, message_text, source_url, unsupported_material),
    )


def _create_and_process_order(order: Order) -> Order:
    saved_order = create_order(order)

    if saved_order.material.startswith("Unsupported:"):
        return saved_order

    pricing_settings = load_pricing_settings()
    processing_result = process_model_url(
        order_id=saved_order.id,
        model_url=saved_order.modelDownloadURL,
        quantity=saved_order.quantity,
        pricing_settings=pricing_settings,
    )

    updated_notes = saved_order.notes or ""
    if updated_notes:
        updated_notes += "\n\n"
    updated_notes += processing_result.reason

    updated_order = saved_order.model_copy(
        update={
            "fileName": processing_result.file_name or saved_order.fileName,
            "shippingAmount": processing_result.shipping_amount or saved_order.shippingAmount,
            "totalAmount": processing_result.total_amount or saved_order.totalAmount,
            "status": _processed_status(saved_order.status, processing_result.downloaded),
            "replyDraft": _processed_reply_draft(saved_order, processing_result),
            "notes": updated_notes,
            "downloadedFilePath": processing_result.downloaded_file_path,
            "estimatedPrintHours": processing_result.estimated_print_hours,
            "estimatedMaterialGrams": processing_result.estimated_material_grams,
        }
    )

    return save_order(updated_order) or updated_order


def _lead_file_name(file_name: Optional[str], model_url: Optional[str]) -> str:
    if file_name:
        return file_name

    if model_url:
        return PurePosixPath(model_url).name or "linked-model"

    return "file-link-needed"


def _lead_status(model_url: Optional[str], unsupported_material: Optional[str]) -> OrderStatus:
    if unsupported_material:
        return OrderStatus.MANUAL_REVIEW

    return OrderStatus.NEW_LEAD if model_url else OrderStatus.MANUAL_REVIEW


def _processed_status(current_status: OrderStatus, downloaded: bool) -> OrderStatus:
    if downloaded:
        return OrderStatus.QUOTED

    return current_status


def _processed_reply_draft(order: Order, processing_result) -> str:
    if not processing_result.downloaded:
        return order.replyDraft

    first_name = order.customerName.split()[0]
    material_text = order.material
    total_amount = processing_result.total_amount or order.totalAmount
    shipping_amount = processing_result.shipping_amount or order.shippingAmount

    return (
        f"Hi {first_name}, I reviewed the file and created a rough quote. "
        f"I can print {order.quantity} unit"
        f"{'' if order.quantity == 1 else 's'} in {material_text} for "
        f"${total_amount:.2f} shipped. "
        f"Shipping is currently estimated at ${shipping_amount:.2f}. "
        "If that works for you, send your color choice and shipping ZIP code and I can move to payment."
    )


def _resolve_requested_material(material_preference: Optional[str], detected_material: Optional[str]) -> Optional[str]:
    if material_preference:
        normalized = material_preference.strip().upper()
        if normalized == "PLA+":
            return "PLA"
        if normalized in {"PLA", "PETG"}:
            return normalized

    return detected_material


def _resolve_unsupported_material(material_preference: Optional[str], detected_unsupported_material: Optional[str]) -> Optional[str]:
    if material_preference:
        normalized = material_preference.strip().upper()
        if normalized not in {"PLA", "PLA+", "PETG"}:
            return material_preference.strip()

    return detected_unsupported_material


def _reddit_message_text(post) -> str:
    pieces = [post.title.strip()]

    if post.selftext.strip():
        pieces.append(post.selftext.strip())

    if post.outbound_url and "reddit.com" not in post.outbound_url:
        pieces.append(post.outbound_url)

    return "\n".join(piece for piece in pieces if piece)
