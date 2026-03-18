from typing import List, Optional
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
    downloadedFilePath: Optional[str] = None
    estimatedPrintHours: Optional[float] = None
    estimatedMaterialGrams: Optional[float] = None
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


class ScoutMessageRequest(BaseModel):
    source: str
    customerName: str
    messageText: str
    sourceURL: Optional[str] = None


class ScoutMessageResponse(BaseModel):
    matched: bool
    reason: str
    order: Optional[Order] = None
    detectedModelURL: Optional[str] = None
    detectedMaterial: Optional[str] = None
    unsupportedMaterial: Optional[str] = None


class RedditScanResponse(BaseModel):
    scannedPosts: int
    importedOrders: int
    skippedPosts: int
    summary: str
    createdOrders: List[Order] = []


class DiscordScanResponse(BaseModel):
    scannedMessages: int
    importedOrders: int
    skippedMessages: int
    summary: str
    createdOrders: List[Order] = []


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
