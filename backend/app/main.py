from uuid import UUID
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import Order, UpdatePaymentLinkRequest, UpdateStatusRequest
from .store import get_order, load_orders, update_order_status, update_payment_link


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


@app.get("/orders/{order_id}", response_model=Order)
def fetch_order(order_id: UUID) -> Order:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


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
