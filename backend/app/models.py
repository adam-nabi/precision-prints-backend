from typing import Optional
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderStatus(str, Enum):
    NEW_LEAD = "New Lead"
    QUOTED = "Quoted"
    PENDING_PAYMENT = "Pending Payment"
    PAID = "Paid"
    PRINTING = "Printing"
    SHIPPED = "Shipped"
    MANUAL_REVIEW = "Manual Review"


class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    customerName: str
    source: str
    fileName: str
    material: str
    color: str
    quantity: int
    shippingAmount: float
    totalAmount: float
    status: OrderStatus
    replyDraft: str
    modelDownloadURL: Optional[str] = None
    paymentLinkURL: Optional[str] = None
    shippingName: Optional[str] = None
    shippingAddress: Optional[str] = None
    shippingZIP: Optional[str] = None
    notes: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: OrderStatus


class UpdatePaymentLinkRequest(BaseModel):
    paymentLinkURL: str


class IntakeLeadRequest(BaseModel):
    source: str
    customerName: str
    messageText: str
    sourceURL: Optional[str] = None
    modelURL: Optional[str] = None
    fileName: Optional[str] = None
    quantity: Optional[int] = 1
    materialPreference: Optional[str] = None
    colorPreference: Optional[str] = None


class PricingSettings(BaseModel):
    baseOrderFee: float
    materialMarkupMultiplier: float
    hourlyPrintRate: float
    complexitySurcharge: float
    shippingMarkupFlat: float


class UpdatePricingSettingsRequest(BaseModel):
    baseOrderFee: float
    materialMarkupMultiplier: float
    hourlyPrintRate: float
    complexitySurcharge: float
    shippingMarkupFlat: float
