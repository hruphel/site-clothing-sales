"""Pydantic-схемы для JSON API.

Цель — отдавать фронту чистые DTO без SQLAlchemy-объектов и без HTML.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    DELIVERY_STATUS_LABELS_RU,
    ORDER_STATUS_LABELS_RU,
    PRODUCT_STATUS_LABELS_RU,
    ROLE_LABELS_RU,
    DeliveryStatus,
    OrderStatus,
    ProductStatus,
    UserRole,
)


# ---------- общее ----------


class APIError(BaseModel):
    """Тип ответа на любые наши HTTPException-ы."""

    detail: str


class MessageResponse(BaseModel):
    detail: str = "ok"


# ---------- auth / users ----------


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: UserRole
    role_label: str

    @classmethod
    def from_model(cls, user) -> "UserOut":  # noqa: ANN001
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            role_label=ROLE_LABELS_RU.get(user.role, user.role.value),
        )


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str
    password: str = Field(min_length=6, max_length=200)
    password_confirm: str
    role: UserRole = UserRole.BUYER


class LoginIn(BaseModel):
    identifier: str
    password: str


# ---------- catalog / products ----------


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: Decimal
    sizes: list[str]
    stock: dict[str, int]
    image_url: str | None
    status: ProductStatus
    status_label: str
    rejection_reason: str | None
    seller_username: str | None
    seller_id: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, p) -> "ProductOut":  # noqa: ANN001
        stock = p.sizes_stock
        # Размеры в каталоге отдаём в порядке хранения; запас — словарём.
        sizes_order = p.sizes_list or list(stock.keys())
        return cls(
            id=p.id,
            name=p.name,
            description=p.description or "",
            price=p.price,
            sizes=sizes_order,
            stock=stock,
            image_url=f"/uploads/{p.image_filename}" if p.image_filename else None,
            status=p.status,
            status_label=PRODUCT_STATUS_LABELS_RU.get(p.status, p.status.value),
            rejection_reason=p.rejection_reason,
            seller_username=p.seller.username if p.seller else None,
            seller_id=p.seller_id,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


# ---------- cart ----------


class CartItemOut(BaseModel):
    id: int
    product: ProductOut
    size: str
    quantity: int
    line_total: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal
    item_count: int


class CartAddIn(BaseModel):
    product_id: int
    size: str = Field(default="", max_length=16)
    quantity: int = Field(default=1, ge=1, le=99)


class CartUpdateIn(BaseModel):
    quantity: int = Field(ge=1, le=99)


# ---------- orders / receipts ----------


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    product_name: str
    product_price: Decimal
    sizes: list[str]
    quantity: int
    line_total: Decimal

    @classmethod
    def from_model(cls, item) -> "OrderItemOut":  # noqa: ANN001
        return cls(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            product_price=item.product_price,
            sizes=[s.strip() for s in (item.sizes or "").split(",") if s.strip()],
            quantity=item.quantity,
            line_total=item.line_total,
        )


class ReceiptOut(BaseModel):
    receipt_number: str
    transaction_id: str
    pdf_url: str
    issued_at: datetime


class OrderOut(BaseModel):
    id: int
    status: OrderStatus
    status_label: str
    total: Decimal
    recipient_name: str
    recipient_phone: str
    delivery_address: str
    comment: str
    created_at: datetime
    paid_at: datetime | None
    items: list[OrderItemOut]
    receipt: ReceiptOut | None
    delivery_status: DeliveryStatus
    delivery_status_label: str
    delivery_visible: bool
    delivery_updated_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    buyer_id: int
    buyer_username: str | None = None
    buyer_email: str | None = None

    @classmethod
    def from_model(cls, order, *, include_buyer: bool = False) -> "OrderOut":  # noqa: ANN001
        return cls(
            id=order.id,
            status=order.status,
            status_label=ORDER_STATUS_LABELS_RU.get(order.status, order.status.value),
            total=order.total,
            recipient_name=order.recipient_name,
            recipient_phone=order.recipient_phone,
            delivery_address=order.delivery_address,
            comment=order.comment or "",
            created_at=order.created_at,
            paid_at=order.paid_at,
            items=[OrderItemOut.from_model(i) for i in order.items],
            receipt=(
                ReceiptOut(
                    receipt_number=order.receipt.receipt_number,
                    transaction_id=order.receipt.transaction_id,
                    pdf_url=f"/receipts/{order.receipt.pdf_filename}",
                    issued_at=order.receipt.issued_at,
                )
                if order.receipt is not None
                else None
            ),
            delivery_status=order.delivery_status,
            delivery_status_label=DELIVERY_STATUS_LABELS_RU.get(
                order.delivery_status, order.delivery_status.value
            ),
            delivery_visible=order.delivery_visible,
            delivery_updated_at=order.delivery_updated_at,
            shipped_at=order.shipped_at,
            delivered_at=order.delivered_at,
            buyer_id=order.buyer_id,
            buyer_username=order.buyer.username if include_buyer and order.buyer else None,
            buyer_email=order.buyer.email if include_buyer and order.buyer else None,
        )


class CheckoutIn(BaseModel):
    recipient_name: str
    recipient_phone: str
    delivery_address: str
    comment: str = ""


class PaymentIn(BaseModel):
    card_number: str
    card_holder: str
    card_expiry: str
    card_cvc: str


class DeliveryUpdateIn(BaseModel):
    delivery_status: DeliveryStatus


# ---------- admin ----------


class RejectIn(BaseModel):
    reason: str


class AdminCountsOut(BaseModel):
    pending: int
    published: int
    rejected: int
    total_users: int


# ---------- enums dump ----------


class EnumValueOut(BaseModel):
    value: str
    label: str


class EnumsOut(BaseModel):
    delivery_statuses: list[EnumValueOut]
    delivery_status_order: list[str]
    order_statuses: list[EnumValueOut]
    product_statuses: list[EnumValueOut]
    user_roles: list[EnumValueOut]


def build_enums() -> EnumsOut:
    return EnumsOut(
        delivery_statuses=[
            EnumValueOut(value=s.value, label=DELIVERY_STATUS_LABELS_RU[s])
            for s in DeliveryStatus
        ],
        delivery_status_order=[s.value for s in DeliveryStatus],
        order_statuses=[
            EnumValueOut(value=s.value, label=ORDER_STATUS_LABELS_RU[s]) for s in OrderStatus
        ],
        product_statuses=[
            EnumValueOut(value=s.value, label=PRODUCT_STATUS_LABELS_RU[s]) for s in ProductStatus
        ],
        user_roles=[EnumValueOut(value=r.value, label=ROLE_LABELS_RU[r]) for r in UserRole],
    )
