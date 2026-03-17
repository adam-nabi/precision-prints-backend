from uuid import UUID
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import Order, UpdateStatusRequest
from .payments import create_payment_link
from .store import get_order, load_orders, save_order, update_order_status


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


@app.post("/orders/{order_id}/payment-link", response_model=Order)
def create_order_payment_link(order_id: UUID) -> Order:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        updated_order = create_payment_link(order)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Stripe error: {error}") from error

    saved_order = save_order(updated_order)
    if saved_order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return saved_order
