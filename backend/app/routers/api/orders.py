"""UC-3 (оформление заказа), UC-4 (имитация оплаты + чек+PDF)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ...config import settings
from ...database import get_db
from ...dependencies import get_current_user
from ...models import (
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    Receipt,
    User,
    UserRole,
)
from ...schemas import CheckoutIn, MessageResponse, OrderOut, PaymentIn
from ...services.receipts import (
    generate_receipt_number,
    generate_transaction_id,
    render_receipt_pdf,
)
from ._common import require_buyer

router = APIRouter(prefix="/orders", tags=["orders"])

NAME_MAX = 160
ADDRESS_MAX = 500
COMMENT_MAX = 1000
PHONE_PATTERN = re.compile(r"^[\d\+\-\(\) ]{6,40}$")


def _active_cart(db: Session, buyer_id: int) -> list[CartItem]:
    items = (
        db.query(CartItem)
        .options(selectinload(CartItem.product))
        .filter(CartItem.buyer_id == buyer_id)
        .all()
    )
    return [i for i in items if i.product.status == ProductStatus.PUBLISHED]


def _decrement_stock_for_order(db: Session, order: Order) -> None:
    """Списывает оплаченные товары со склада по выбранному размеру.

    Работает по факту перехода заказа в PAID. Перед каждым декрементом снова
    подгружает Product, чтобы не сесть на устаревший кэш. Если товар уже удалён
    или поле размера в позиции не совпадает с ключом в `sizes_stock` (например,
    старая позиция без явного размера), эту строку пропускаем — лучше тихо,
    чем уронить оплату уже совершённого заказа. Уйти ниже нуля не позволяем.
    """
    for item in order.items:
        if item.product_id is None:
            continue
        product = db.get(Product, item.product_id)
        if product is None:
            continue
        stock = product.sizes_stock
        if not stock:
            continue
        size_key = (item.sizes or "").strip()
        if not size_key or size_key not in stock:
            continue
        stock[size_key] = max(0, stock[size_key] - int(item.quantity or 0))
        product.stock_json = json.dumps(stock, ensure_ascii=False)


def _own_order_or_404(db: Session, buyer: User, order_id: int) -> Order:
    order = (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.receipt))
        .filter(Order.id == order_id, Order.buyer_id == buyer.id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден.")
    return order


@router.get("", response_model=list[OrderOut])
def list_orders(buyer: User = Depends(require_buyer), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.receipt))
        .filter(Order.buyer_id == buyer.id)
        .order_by(desc(Order.created_at))
        .all()
    )
    return [OrderOut.from_model(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
def order_detail(
    order_id: int,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    order = _own_order_or_404(db, buyer, order_id)
    return OrderOut.from_model(order)


@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutIn,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    items = _active_cart(db, buyer.id)
    if not items:
        raise HTTPException(status_code=400, detail="Корзина пуста.")

    name = payload.recipient_name.strip()
    phone = payload.recipient_phone.strip()
    address = payload.delivery_address.strip()
    comment_clean = payload.comment.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Укажите имя получателя.")
    if len(name) > NAME_MAX:
        raise HTTPException(status_code=400, detail=f"Имя получателя не должно быть длиннее {NAME_MAX} символов.")
    if not phone:
        raise HTTPException(status_code=400, detail="Укажите телефон.")
    if not PHONE_PATTERN.match(phone):
        raise HTTPException(status_code=400, detail="Телефон должен содержать 6–40 символов: цифры, пробелы, +, -, (, ).")
    if not address:
        raise HTTPException(status_code=400, detail="Укажите адрес доставки.")
    if len(address) > ADDRESS_MAX:
        raise HTTPException(status_code=400, detail=f"Адрес не должен быть длиннее {ADDRESS_MAX} символов.")
    if len(comment_clean) > COMMENT_MAX:
        raise HTTPException(status_code=400, detail=f"Комментарий не должен быть длиннее {COMMENT_MAX} символов.")

    total = sum((i.line_total for i in items), Decimal("0.00"))
    order = Order(
        buyer_id=buyer.id,
        status=OrderStatus.CREATED,
        total=total,
        recipient_name=name,
        recipient_phone=phone,
        delivery_address=address,
        comment=comment_clean,
    )
    db.add(order)
    db.flush()
    for ci in items:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=ci.product.id,
                product_name=ci.product.name,
                product_price=ci.product.price,
                sizes=ci.size or ci.product.sizes,
                quantity=ci.quantity,
            )
        )
    db.query(CartItem).filter(CartItem.buyer_id == buyer.id).delete()
    db.commit()
    db.refresh(order)
    return OrderOut.from_model(order)


@router.post("/{order_id}/pay", response_model=OrderOut)
def pay(
    order_id: int,
    payload: PaymentIn,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    order = _own_order_or_404(db, buyer, order_id)
    if order.status != OrderStatus.CREATED:
        raise HTTPException(status_code=409, detail="Этот заказ уже оплачен или отменён.")

    digits_only = re.sub(r"\s+", "", payload.card_number)
    if not digits_only.isdigit() or not (12 <= len(digits_only) <= 19):
        raise HTTPException(status_code=400, detail="Номер карты должен содержать 12–19 цифр.")
    if not payload.card_holder.strip():
        raise HTTPException(status_code=400, detail="Укажите владельца карты.")
    if not re.match(r"^\d{2}/\d{2}$", payload.card_expiry.strip()):
        raise HTTPException(status_code=400, detail="Срок действия — в формате MM/YY.")
    if not re.match(r"^\d{3,4}$", payload.card_cvc.strip()):
        raise HTTPException(status_code=400, detail="CVC — 3 или 4 цифры.")

    issued_at = datetime.now(timezone.utc)
    receipt_number = generate_receipt_number(issued_at)
    transaction_id = generate_transaction_id()

    order.status = OrderStatus.PAID
    order.paid_at = issued_at
    order.delivery_updated_at = issued_at
    _decrement_stock_for_order(db, order)
    pdf_filename = render_receipt_pdf(order, receipt_number, transaction_id, issued_at)
    receipt = Receipt(
        order_id=order.id,
        receipt_number=receipt_number,
        transaction_id=transaction_id,
        pdf_filename=pdf_filename,
    )
    db.add(receipt)
    db.commit()
    db.refresh(order)
    return OrderOut.from_model(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(
    order_id: int,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    order = _own_order_or_404(db, buyer, order_id)
    if order.status != OrderStatus.CREATED:
        raise HTTPException(status_code=409, detail="Отменить можно только неоплаченный заказ.")
    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    return OrderOut.from_model(order)


# --- скачивание чека (отдельный роутер на /receipts) ---


receipts_router = APIRouter(prefix="/receipts", tags=["receipts"])


@receipts_router.get("/{filename}")
def download_receipt(
    filename: str,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(r"^RCP-\d{8}-[A-F0-9]{6}\.pdf$", filename):
        raise HTTPException(status_code=404, detail="Чек не найден.")
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")
    receipt = (
        db.query(Receipt)
        .options(selectinload(Receipt.order))
        .filter(Receipt.pdf_filename == filename)
        .first()
    )
    if receipt is None:
        raise HTTPException(status_code=404, detail="Чек не найден.")
    if receipt.order.buyer_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён.")
    path = settings.receipts_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл чека отсутствует.")
    return FileResponse(path=str(path), media_type="application/pdf", filename=filename)


__all__ = ["router", "receipts_router"]
