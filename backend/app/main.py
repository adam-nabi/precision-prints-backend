from pathlib import PurePosixPath
from uuid import UUID, uuid4
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    IntakeLeadRequest,
    Order,
    OrderStatus,
    PricingSettings,
    UpdatePaymentLinkRequest,
    UpdatePricingSettingsRequest,
    UpdateStatusRequest,
)
from .store import (
    create_order,
    delete_order,
    get_order,
    load_orders,
    load_pricing_settings,
    save_pricing_settings,
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


@app.post("/lead-intake", response_model=Order, status_code=201)
def intake_lead(request: IntakeLeadRequest) -> Order:
    imported_order = Order(
        id=uuid4(),
        customerName=request.customerName,
        source=request.source,
        fileName=_lead_file_name(request),
        material=request.materialPreference or "Not specified",
        color=request.colorPreference or "Not specified",
        quantity=max(request.quantity or 1, 1),
        shippingAmount=0.0,
        totalAmount=0.0,
        status=OrderStatus.NEW_LEAD if request.modelURL else OrderStatus.MANUAL_REVIEW,
        replyDraft=_lead_reply_draft(request),
        modelDownloadURL=request.modelURL,
        notes=_lead_notes(request),
    )
    return create_order(imported_order)


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


def _lead_file_name(request: IntakeLeadRequest) -> str:
    if request.fileName:
        return request.fileName

    if request.modelURL:
        return PurePosixPath(request.modelURL).name or "linked-model"

    return "file-link-needed"


def _lead_reply_draft(request: IntakeLeadRequest) -> str:
    first_name = request.customerName.split()[0]

    if request.modelURL:
        return (
            f"Hi {first_name}, thanks for sharing the model link. "
            "I can review it and get you a quote. "
            "Please send your preferred material, color, quantity, and shipping ZIP code."
        )

    return (
        f"Hi {first_name}, thanks for reaching out. "
        "Please send the STL, 3MF, ZIP, Thingiverse, Printables, or MakerWorld link, "
        "plus your preferred material, color, quantity, and shipping ZIP code."
    )


def _lead_notes(request: IntakeLeadRequest) -> str:
    note_lines = [f"Imported lead from {request.source}."]

    if request.sourceURL:
        note_lines.append(f"Source URL: {request.sourceURL}")

    note_lines.append("Original message:")
    note_lines.append(request.messageText)

    return "\n".join(note_lines)
